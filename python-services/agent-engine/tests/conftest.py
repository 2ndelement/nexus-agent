"""
tests/conftest.py — 公共 fixtures 和测试配置

- 所有 LLM 调用使用 Mock，不消耗真实 API 配额
- MySQL checkpointer 使用 MemorySaver（内存中），不依赖真实 DB 环境
- pytest-asyncio 使用 auto 模式
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, AIMessageChunk
from langgraph.checkpoint.memory import MemorySaver

# ─────────────────────────── pytest-asyncio 配置 ───────────────────────────
# 设置为 auto 模式，所有 async 测试函数自动被标记
pytest_plugins = ("pytest_asyncio",)


# ─────────────────────────── Mock LLM Response ───────────────────────────

def make_mock_llm(response_text: str = "你好，我是 AI 助手！"):
    """
    创建一个 Mock ChatOpenAI，ainvoke 返回 AIMessage，
    astream 逐字符 yield AIMessageChunk。
    """
    mock_llm = MagicMock()

    async def fake_ainvoke(messages, **kwargs):
        return AIMessage(content=response_text)

    async def fake_astream(messages, **kwargs):
        for char in response_text:
            yield AIMessageChunk(content=char)

    mock_llm.ainvoke = AsyncMock(side_effect=fake_ainvoke)
    mock_llm.astream = fake_astream
    return mock_llm


# ─────────────────────────── Checkpointer Fixture ───────────────────────────

@pytest.fixture
def memory_checkpointer():
    """返回内存 checkpointer（MemorySaver），无需真实 MySQL。"""
    return MemorySaver()


# ─────────────────────────── Graph Fixture ───────────────────────────

@pytest.fixture
def mock_graph(memory_checkpointer):
    """
    构建使用 MemorySaver 的测试图，并 patch LLM 为 Mock。
    """
    from app.agent.graph import build_graph

    with patch("app.agent.nodes._build_llm", return_value=make_mock_llm()):
        graph = build_graph(checkpointer=memory_checkpointer)
        yield graph


@pytest.fixture
def mock_graph_factory(memory_checkpointer):
    """
    返回一个工厂函数，可以指定 response_text，用于多租户隔离测试。
    每次调用返回一个新的 graph（共享同一个 checkpointer）。
    """
    from app.agent.graph import build_graph

    def _factory(response_text: str = "AI 回复"):
        with patch("app.agent.nodes._build_llm", return_value=make_mock_llm(response_text)):
            return build_graph(checkpointer=memory_checkpointer)

    return _factory


# ─────────────────────────── FastAPI TestClient Fixture ───────────────────────────

@pytest.fixture
def test_app(memory_checkpointer):
    """
    返回 FastAPI TestClient。
    - checkpointer 替换为 MemorySaver（内存）
    - LLM 替换为 Mock
    """
    from app.agent.graph import build_graph
    from app.api.v1.chat import router
    from main import app

    with patch("app.agent.nodes._build_llm", return_value=make_mock_llm()):
        with patch(
            "app.api.v1.chat.get_mysql_checkpointer"
        ) as mock_cp_ctx:
            # 使 get_mysql_checkpointer() async context manager 返回 MemorySaver
            from contextlib import asynccontextmanager

            @asynccontextmanager
            async def fake_checkpointer_ctx():
                yield memory_checkpointer

            mock_cp_ctx.return_value = fake_checkpointer_ctx()
            mock_cp_ctx.side_effect = lambda: fake_checkpointer_ctx()

            client = TestClient(app, raise_server_exceptions=False)
            yield client


@pytest.fixture
def default_headers():
    """默认请求 Header（模拟 Java Gateway 注入）。"""
    return {
        "X-Tenant-Id": "tenant-A",
        "X-User-Id": "user-001",
        "X-Conv-Id": "conv-001",
    }
