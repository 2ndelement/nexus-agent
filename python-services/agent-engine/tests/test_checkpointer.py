"""
tests/test_checkpointer.py — Checkpointer 隔离测试

覆盖场景：
1. 多租户隔离：租户A 的会话历史不影响租户B 同 conv_id
   - 租户A 对话后，租户B 用同 conversation_id 对话，历史应为空
2. 会话连续性：同 tenant+conversation_id 第二轮能看到第一轮历史
3. MySQL checkpointer 持久化：Agent 执行后 checkpoint 中有记录
4. thread_id 隔离语义验证：不同 thread_id 完全独立
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver


# ─────────────────────────── Helper ───────────────────────────

def make_mock_llm(response_text: str = "AI 回复"):
    mock_llm = MagicMock()

    async def fake_ainvoke(messages, **kwargs):
        return AIMessage(content=response_text)

    mock_llm.ainvoke = AsyncMock(side_effect=fake_ainvoke)
    return mock_llm


def build_test_graph(checkpointer, response_text="AI 回复"):
    """构建使用指定 checkpointer 的测试图。"""
    from app.agent.graph import build_graph
    with patch("app.agent.nodes._build_llm", return_value=make_mock_llm(response_text)):
        return build_graph(checkpointer=checkpointer)


# ─────────────────────────── 多租户隔离测试 ───────────────────────────

@pytest.mark.asyncio
async def test_multi_tenant_isolation_same_conv_id():
    """
    核心测试：多租户隔离 — 租户A 的会话历史不影响租户B

    场景：
    1. 租户A 用 conv-001 发送 "你好"，AI 回复 "租户A的回复"
    2. 租户B 用同样的 conv-001 发送 "你好"
    3. 租户B 看到的历史应为空（只有本轮消息），不包含租户A的内容

    原理：
    - 租户A thread_id = "tenant-A:conv-001"
    - 租户B thread_id = "tenant-B:conv-001"
    - 两个 thread_id 完全不同，checkpoint 完全隔离
    """
    from app.agent.graph import build_graph, make_config

    saver = MemorySaver()  # 共享同一个 checkpointer（模拟生产中共享 MySQL）
    same_conv_id = "conv-shared-001"

    # 步骤1：租户A 对话
    with patch("app.agent.nodes._build_llm", return_value=make_mock_llm("租户A的回复")):
        graph_a = build_graph(checkpointer=saver)
        config_a = make_config("tenant-A", same_conv_id)
        result_a = await graph_a.ainvoke(
            {
                "messages": [HumanMessage(content="我是租户A的消息")],
                "tenant_id": "tenant-A",
                "user_id": "user-a",
                "conversation_id": same_conv_id,
            },
            config_a,
        )

    assert len(result_a["messages"]) == 2
    # 验证 checkpoint 已保存
    checkpoint_a = await saver.aget(config_a)
    assert checkpoint_a is not None, "租户A的 checkpoint 应已保存"

    # 步骤2：租户B 用同 conv_id 对话
    with patch("app.agent.nodes._build_llm", return_value=make_mock_llm("租户B的回复")):
        graph_b = build_graph(checkpointer=saver)
        config_b = make_config("tenant-B", same_conv_id)
        result_b = await graph_b.ainvoke(
            {
                "messages": [HumanMessage(content="我是租户B的消息")],
                "tenant_id": "tenant-B",
                "user_id": "user-b",
                "conversation_id": same_conv_id,
            },
            config_b,
        )

    # 步骤3：验证租户B 的历史中不包含租户A 的内容
    messages_b = result_b["messages"]
    contents_b = [m.content for m in messages_b]

    assert "我是租户A的消息" not in contents_b, (
        "租户B 的历史不应包含租户A 的 Human 消息！"
    )
    assert "租户A的回复" not in contents_b, (
        "租户B 的历史不应包含租户A 的 AI 回复！"
    )
    assert "我是租户B的消息" in contents_b, "租户B 的历史应包含自己的消息"
    assert "租户B的回复" in contents_b, "租户B 的历史应包含自己的 AI 回复"

    # 租户B 第一轮对话应只有2条消息（Human + AI）
    assert len(messages_b) == 2, (
        f"租户B 的首轮消息数应为 2，实际为 {len(messages_b)}。"
        f"消息内容: {contents_b}"
    )


@pytest.mark.asyncio
async def test_multi_tenant_different_convs_isolated():
    """
    额外隔离测试：不同租户不同 conv_id 也完全隔离
    """
    from app.agent.graph import build_graph, make_config

    saver = MemorySaver()

    with patch("app.agent.nodes._build_llm", return_value=make_mock_llm("回复1")):
        g1 = build_graph(checkpointer=saver)
        r1 = await g1.ainvoke(
            {"messages": [HumanMessage(content="A的消息")],
             "tenant_id": "t1", "user_id": "u1", "conversation_id": "c1"},
            make_config("t1", "c1"),
        )

    with patch("app.agent.nodes._build_llm", return_value=make_mock_llm("回复2")):
        g2 = build_graph(checkpointer=saver)
        r2 = await g2.ainvoke(
            {"messages": [HumanMessage(content="B的消息")],
             "tenant_id": "t2", "user_id": "u2", "conversation_id": "c2"},
            make_config("t2", "c2"),
        )

    assert len(r1["messages"]) == 2
    assert len(r2["messages"]) == 2
    assert "A的消息" not in [m.content for m in r2["messages"]]
    assert "B的消息" not in [m.content for m in r1["messages"]]


# ─────────────────────────── 会话连续性测试 ───────────────────────────

@pytest.mark.asyncio
async def test_same_tenant_conversation_continuity():
    """
    场景2：同租户同 conv_id 多轮对话保持历史

    同一个 (tenant_id, conv_id) 对应同一个 thread_id，
    checkpoint 中的历史会随每轮追加。
    """
    from app.agent.graph import build_graph, make_config

    saver = MemorySaver()
    config = make_config("tenant-A", "conv-multi-turn")

    # 第一轮
    with patch("app.agent.nodes._build_llm", return_value=make_mock_llm("首轮AI")):
        g = build_graph(checkpointer=saver)
        r1 = await g.ainvoke(
            {"messages": [HumanMessage(content="首轮Human")],
             "tenant_id": "tenant-A", "user_id": "u", "conversation_id": "conv-multi-turn"},
            config,
        )
    assert len(r1["messages"]) == 2

    # 第二轮
    with patch("app.agent.nodes._build_llm", return_value=make_mock_llm("次轮AI")):
        g = build_graph(checkpointer=saver)
        r2 = await g.ainvoke(
            {"messages": [HumanMessage(content="次轮Human")],
             "tenant_id": "tenant-A", "user_id": "u", "conversation_id": "conv-multi-turn"},
            config,
        )

    assert len(r2["messages"]) == 4, (
        f"第二轮应有4条消息，实际: {len(r2['messages'])}"
    )
    contents = [m.content for m in r2["messages"]]
    assert "首轮Human" in contents
    assert "首轮AI" in contents
    assert "次轮Human" in contents
    assert "次轮AI" in contents


# ─────────────────────────── Checkpoint 持久化测试 ───────────────────────────

@pytest.mark.asyncio
async def test_checkpoint_saved_after_agent_run():
    """
    场景3：MySQL checkpointer 持久化 — Agent 执行后 checkpoint 有记录

    使用 MemorySaver 模拟：执行后 saver.aget(config) 应返回非 None。
    """
    from app.agent.graph import build_graph, make_config

    saver = MemorySaver()
    config = make_config("tenant-persist", "conv-persist-001")

    with patch("app.agent.nodes._build_llm", return_value=make_mock_llm("持久化测试")):
        graph = build_graph(checkpointer=saver)
        await graph.ainvoke(
            {"messages": [HumanMessage(content="测试持久化")],
             "tenant_id": "tenant-persist", "user_id": "u",
             "conversation_id": "conv-persist-001"},
            config,
        )

    checkpoint = await saver.aget(config)
    assert checkpoint is not None, "Agent 执行后 checkpoint 应已保存"

    # 验证 checkpoint 内容包含消息历史
    channel_values = checkpoint.get("channel_values", {})
    assert "messages" in channel_values, "checkpoint 应包含 messages 字段"
    saved_messages = channel_values["messages"]
    assert len(saved_messages) >= 2, "checkpoint 应包含至少2条消息"


# ─────────────────────────── thread_id 格式测试 ───────────────────────────

def test_thread_id_format_strict():
    """
    验证 make_config 生成的 thread_id 严格遵循 f"{tenant_id}:{conversation_id}" 格式

    这是 Code Review 检查清单第一项。
    """
    from app.agent.graph import make_config

    test_cases = [
        ("tenant-001", "conv-abc", "tenant-001:conv-abc"),
        ("org_xyz", "session_123", "org_xyz:session_123"),
        ("t", "c", "t:c"),
        ("multi.part.tenant", "conv/with/slash", "multi.part.tenant:conv/with/slash"),
    ]

    for tenant_id, conv_id, expected_thread_id in test_cases:
        config = make_config(tenant_id, conv_id)
        actual = config["configurable"]["thread_id"]
        assert actual == expected_thread_id, (
            f"thread_id 格式错误: 期望 '{expected_thread_id}'，实际 '{actual}'"
        )


@pytest.mark.asyncio
async def test_thread_id_isolation_in_memory():
    """
    验证 MemorySaver 确实按 thread_id 隔离存储，
    不同 thread_id 的 checkpoint 互不影响。
    """
    from app.agent.graph import make_config

    saver = MemorySaver()
    config_a = make_config("tenant-A", "conv-X")
    config_b = make_config("tenant-B", "conv-X")  # 相同 conv_id，不同 tenant

    thread_id_a = config_a["configurable"]["thread_id"]
    thread_id_b = config_b["configurable"]["thread_id"]

    # thread_id 不同
    assert thread_id_a != thread_id_b

    # 初始时两个 thread 均无 checkpoint
    cp_a = await saver.aget(config_a)
    cp_b = await saver.aget(config_b)
    assert cp_a is None
    assert cp_b is None
