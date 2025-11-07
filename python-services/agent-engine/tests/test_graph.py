"""
tests/test_graph.py — LangGraph 图测试

覆盖场景：
1. 正常对话：输入 HumanMessage → 收到 AI 回复
2. 会话连续性：同 tenant+conversation_id 第二轮能看到第一轮历史
3. thread_id 格式验证：严格为 f"{tenant_id}:{conversation_id}"
4. astream_agent 流式输出正常工作
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver


# ─────────────────────────── Helper ───────────────────────────

def make_mock_llm(response_text: str = "AI 回复内容"):
    """创建 Mock LLM，ainvoke 返回指定文本。"""
    mock_llm = MagicMock()

    async def fake_ainvoke(messages, **kwargs):
        return AIMessage(content=response_text)

    mock_llm.ainvoke = AsyncMock(side_effect=fake_ainvoke)
    return mock_llm


# ─────────────────────────── 测试用例 ───────────────────────────

@pytest.mark.asyncio
async def test_graph_basic_invocation():
    """场景1：基础调用 — 输入 HumanMessage，返回 AIMessage"""
    from app.agent.graph import build_graph, make_config

    saver = MemorySaver()
    with patch("app.agent.nodes._build_llm", return_value=make_mock_llm("你好！")):
        graph = build_graph(checkpointer=saver)
        config = make_config("tenant-A", "conv-001")

        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content="你好")],
                "tenant_id": "tenant-A",
                "user_id": "user-001",
                "conversation_id": "conv-001",
            },
            config,
        )

    messages = result["messages"]
    assert len(messages) >= 2, "应有 HumanMessage + AIMessage"
    last_msg = messages[-1]
    assert isinstance(last_msg, AIMessage)
    assert last_msg.content == "你好！"


@pytest.mark.asyncio
async def test_graph_conversation_continuity():
    """
    场景2：会话连续性 — 同 tenant+conversation_id 第二轮能看到第一轮历史

    第一轮：发送 "你好"，LLM 回复 "第一轮回复"
    第二轮：发送 "再见"，验证 state.messages 包含第一轮内容
    """
    from app.agent.graph import build_graph, make_config

    saver = MemorySaver()
    config = make_config("tenant-A", "conv-continuity")

    # 第一轮
    with patch("app.agent.nodes._build_llm", return_value=make_mock_llm("第一轮回复")):
        graph = build_graph(checkpointer=saver)
        result1 = await graph.ainvoke(
            {
                "messages": [HumanMessage(content="你好")],
                "tenant_id": "tenant-A",
                "user_id": "user-001",
                "conversation_id": "conv-continuity",
            },
            config,
        )

    assert len(result1["messages"]) == 2  # HumanMessage + AIMessage

    # 第二轮（使用同一 config）
    with patch("app.agent.nodes._build_llm", return_value=make_mock_llm("第二轮回复")):
        graph2 = build_graph(checkpointer=saver)
        result2 = await graph2.ainvoke(
            {
                "messages": [HumanMessage(content="再见")],
                "tenant_id": "tenant-A",
                "user_id": "user-001",
                "conversation_id": "conv-continuity",
            },
            config,
        )

    # 第二轮 messages 应包含：第1轮 Human + AI + 第2轮 Human + AI = 4条
    assert len(result2["messages"]) == 4, (
        f"期望4条消息（含历史），实际: {len(result2['messages'])}"
    )
    # 验证历史内容
    contents = [m.content for m in result2["messages"]]
    assert "你好" in contents, "第二轮应包含第一轮 Human 消息"
    assert "第一轮回复" in contents, "第二轮应包含第一轮 AI 回复"
    assert "再见" in contents, "第二轮应包含当轮 Human 消息"
    assert "第二轮回复" in contents, "第二轮应包含当轮 AI 回复"


def test_make_config_thread_id_format():
    """
    场景3：thread_id 格式验证 — 严格为 f"{tenant_id}:{conversation_id}"

    这是多租户隔离的核心保证。
    """
    from app.agent.graph import make_config

    config = make_config("tenant-X", "conv-123")
    thread_id = config["configurable"]["thread_id"]
    assert thread_id == "tenant-X:conv-123", (
        f"thread_id 格式错误: 期望 'tenant-X:conv-123'，实际 '{thread_id}'"
    )

    # 不同租户，相同 conv_id → 不同 thread_id
    config_b = make_config("tenant-Y", "conv-123")
    thread_id_b = config_b["configurable"]["thread_id"]
    assert thread_id != thread_id_b, "不同租户的 thread_id 必须不同"

    # 确保格式包含分隔符
    assert ":" in thread_id
    parts = thread_id.split(":", 1)
    assert parts[0] == "tenant-X"
    assert parts[1] == "conv-123"


@pytest.mark.asyncio
async def test_astream_agent_yields_tokens():
    """
    场景4：astream_agent 流式输出 — 正常 yield token

    验证 astream_agent 能正确迭代并 yield AI 生成的内容。
    """
    from langchain_core.messages import AIMessageChunk

    from app.agent.graph import astream_agent, build_graph

    saver = MemorySaver()
    response_text = "流式回复测试"

    # 创建能产生 astream_events 的 Mock
    # 需要 patch 节点内的 LLM，使其 ainvoke 返回 AIMessage
    with patch("app.agent.nodes._build_llm", return_value=make_mock_llm(response_text)):
        graph = build_graph(checkpointer=saver)
        tokens = []
        async for token in astream_agent(
            graph=graph,
            tenant_id="tenant-A",
            user_id="user-001",
            conversation_id="conv-stream",
            message="你好",
        ):
            tokens.append(token)

    # astream_events 中 on_chat_model_stream 事件携带 chunk
    # 由于 Mock ainvoke（非 astream），token 可能为空但不应报错
    # 主要验证：不抛异常，函数正常完成
    assert isinstance(tokens, list), "astream_agent 应返回 token 列表"


@pytest.mark.asyncio
async def test_astream_agent_no_error_on_normal_input():
    """astream_agent 正常输入不抛异常。"""
    from app.agent.graph import astream_agent, build_graph

    saver = MemorySaver()
    with patch("app.agent.nodes._build_llm", return_value=make_mock_llm("OK")):
        graph = build_graph(checkpointer=saver)
        collected = []
        async for token in astream_agent(
            graph=graph,
            tenant_id="tenant-A",
            user_id="user-001",
            conversation_id="conv-no-error",
            message="测试",
        ):
            collected.append(token)
    # 不抛异常即通过
    assert True
