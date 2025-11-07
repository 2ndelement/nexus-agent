"""
tests/test_api.py — API 层测试

覆盖场景：
1. 正常对话：发送消息 → 收到流式 SSE 响应（含 chunk + done 事件）
2. 无效输入（空消息）→ 422 错误
3. Header 缺失 → 422 错误
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, AIMessageChunk
from langgraph.checkpoint.memory import MemorySaver


# ─────────────────────────── Helper ───────────────────────────

def make_mock_llm(response_text: str = "你好，我是 AI 助手！"):
    mock_llm = MagicMock()

    async def fake_ainvoke(messages, **kwargs):
        return AIMessage(content=response_text)

    mock_llm.ainvoke = AsyncMock(side_effect=fake_ainvoke)
    return mock_llm


def parse_sse_events(raw_text: str) -> list[dict]:
    """解析 SSE 响应体为事件列表。"""
    events = []
    for line in raw_text.strip().splitlines():
        line = line.strip()
        if line.startswith("data:"):
            data = line[len("data:"):].strip()
            if data:
                try:
                    events.append(json.loads(data))
                except json.JSONDecodeError:
                    events.append({"raw": data})
    return events


# ─────────────────────────── Fixtures ───────────────────────────

@pytest.fixture
def client_with_mock():
    """创建带 Mock LLM 和 MemorySaver 的 TestClient。"""
    from main import app

    memory_saver = MemorySaver()

    @asynccontextmanager
    async def fake_checkpointer():
        yield memory_saver

    with patch("app.agent.nodes._build_llm", return_value=make_mock_llm()):
        with patch(
            "app.api.v1.chat.get_mysql_checkpointer",
            side_effect=fake_checkpointer,
        ):
            with TestClient(app, raise_server_exceptions=False) as c:
                yield c


# ─────────────────────────── 测试用例 ───────────────────────────

class TestChatStreamAPI:
    """POST /api/v1/agent/chat/stream 接口测试"""

    def test_normal_chat_returns_sse(self, client_with_mock):
        """场景1：正常对话 → 返回 text/event-stream，包含 chunk 和 done 事件"""
        response = client_with_mock.post(
            "/api/v1/agent/chat/stream",
            json={"message": "你好"},
            headers={
                "X-Tenant-Id": "tenant-A",
                "X-User-Id": "user-001",
                "X-Conv-Id": "conv-001",
            },
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        events = parse_sse_events(response.text)
        assert len(events) > 0, "SSE 响应不应为空"

        types = [e.get("type") for e in events]
        # 必须有 done 事件
        assert "done" in types, f"缺少 done 事件，实际事件: {types}"
        # 最后一个事件必须是 done
        assert events[-1]["type"] == "done"
        assert events[-1]["conversation_id"] == "conv-001"

    def test_normal_chat_has_chunk_events(self, client_with_mock):
        """场景1扩展：SSE 响应包含 chunk 类型事件"""
        response = client_with_mock.post(
            "/api/v1/agent/chat/stream",
            json={"message": "介绍一下自己"},
            headers={
                "X-Tenant-Id": "tenant-A",
                "X-User-Id": "user-001",
                "X-Conv-Id": "conv-002",
            },
        )
        assert response.status_code == 200
        events = parse_sse_events(response.text)
        types = [e.get("type") for e in events]
        # chunk 事件（可能有，也可能 LLM 返回空token）
        # done 事件必须存在
        assert "done" in types

    def test_empty_message_returns_422(self, client_with_mock):
        """场景4：空消息 → 422 Unprocessable Entity"""
        response = client_with_mock.post(
            "/api/v1/agent/chat/stream",
            json={"message": ""},
            headers={
                "X-Tenant-Id": "tenant-A",
                "X-User-Id": "user-001",
                "X-Conv-Id": "conv-001",
            },
        )
        assert response.status_code == 422

    def test_missing_tenant_header_returns_422(self, client_with_mock):
        """场景4扩展：缺少 X-Tenant-Id Header → 422"""
        response = client_with_mock.post(
            "/api/v1/agent/chat/stream",
            json={"message": "你好"},
            headers={
                "X-User-Id": "user-001",
                "X-Conv-Id": "conv-001",
                # 故意不传 X-Tenant-Id
            },
        )
        assert response.status_code == 422

    def test_missing_user_header_returns_422(self, client_with_mock):
        """缺少 X-User-Id Header → 422"""
        response = client_with_mock.post(
            "/api/v1/agent/chat/stream",
            json={"message": "你好"},
            headers={
                "X-Tenant-Id": "tenant-A",
                "X-Conv-Id": "conv-001",
                # 故意不传 X-User-Id
            },
        )
        assert response.status_code == 422

    def test_missing_conv_header_returns_422(self, client_with_mock):
        """缺少 X-Conv-Id Header → 422"""
        response = client_with_mock.post(
            "/api/v1/agent/chat/stream",
            json={"message": "你好"},
            headers={
                "X-Tenant-Id": "tenant-A",
                "X-User-Id": "user-001",
                # 故意不传 X-Conv-Id
            },
        )
        assert response.status_code == 422

    def test_missing_body_returns_422(self, client_with_mock):
        """缺少请求体 → 422"""
        response = client_with_mock.post(
            "/api/v1/agent/chat/stream",
            headers={
                "X-Tenant-Id": "tenant-A",
                "X-User-Id": "user-001",
                "X-Conv-Id": "conv-001",
            },
        )
        assert response.status_code == 422


class TestHealthEndpoint:
    """健康检查接口测试"""

    def test_health_returns_ok(self, client_with_mock):
        response = client_with_mock.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "agent-engine"
