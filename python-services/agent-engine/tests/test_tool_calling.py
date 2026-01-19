"""
Agent Engine — Tool Calling 单元测试。

测试工具节点和条件路由逻辑。
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.nodes import should_continue, tool_call_node
from app.agent.state import AgentState


# ── should_continue 条件路由测试 ──


def test_should_continue_with_tool_calls():
    """LLM 返回 tool_calls → 路由到 tool_call 节点。"""
    ai_msg = AIMessage(content="", tool_calls=[
        {"id": "call_1", "name": "calculator", "args": {"expression": "2+3"}}
    ])
    state: AgentState = {
        "messages": [HumanMessage(content="2+3=?"), ai_msg],
        "tenant_id": "t1",
        "user_id": "u1",
        "conversation_id": "c1",
    }
    assert should_continue(state) == "tool_call"


def test_should_continue_without_tool_calls():
    """LLM 返回纯文本 → 路由到 end。"""
    ai_msg = AIMessage(content="你好！")
    state: AgentState = {
        "messages": [HumanMessage(content="你好"), ai_msg],
        "tenant_id": "t1",
        "user_id": "u1",
        "conversation_id": "c1",
    }
    assert should_continue(state) == "end"


def test_should_continue_empty_messages():
    """空消息列表 → 路由到 end。"""
    state: AgentState = {
        "messages": [],
        "tenant_id": "t1",
        "user_id": "u1",
        "conversation_id": "c1",
    }
    assert should_continue(state) == "end"


# ── tool_call_node 测试 ──


@pytest.mark.asyncio
@patch("app.agent.nodes._execute_tool", new_callable=AsyncMock)
async def test_tool_call_node_executes_tools(mock_execute):
    """tool_call_node 应调用 _execute_tool 并返回 ToolMessage。"""
    mock_execute.return_value = "5"

    ai_msg = AIMessage(content="", tool_calls=[
        {"id": "call_1", "name": "calculator", "args": {"expression": "2+3"}}
    ])
    state: AgentState = {
        "messages": [HumanMessage(content="2+3"), ai_msg],
        "tenant_id": "t1",
        "user_id": "u1",
        "conversation_id": "c1",
    }

    result = await tool_call_node(state)

    assert len(result["messages"]) == 1
    tool_msg = result["messages"][0]
    assert isinstance(tool_msg, ToolMessage)
    assert tool_msg.content == "5"
    assert tool_msg.tool_call_id == "call_1"
    mock_execute.assert_called_once_with("calculator", {"expression": "2+3"})


@pytest.mark.asyncio
async def test_tool_call_node_no_tool_calls():
    """没有 tool_calls 时应返回空消息列表。"""
    ai_msg = AIMessage(content="没有工具调用")
    state: AgentState = {
        "messages": [ai_msg],
        "tenant_id": "t1",
        "user_id": "u1",
        "conversation_id": "c1",
    }

    result = await tool_call_node(state)
    assert result["messages"] == []


@pytest.mark.asyncio
@patch("app.agent.nodes._execute_tool", new_callable=AsyncMock)
async def test_tool_call_node_multiple_tools(mock_execute):
    """多个工具调用应全部执行。"""
    mock_execute.side_effect = ["5", "搜索结果"]

    ai_msg = AIMessage(content="", tool_calls=[
        {"id": "call_1", "name": "calculator", "args": {"expression": "2+3"}},
        {"id": "call_2", "name": "web_search", "args": {"query": "weather"}},
    ])
    state: AgentState = {
        "messages": [HumanMessage(content="test"), ai_msg],
        "tenant_id": "t1",
        "user_id": "u1",
        "conversation_id": "c1",
    }

    result = await tool_call_node(state)

    assert len(result["messages"]) == 2
    assert result["messages"][0].content == "5"
    assert result["messages"][1].content == "搜索结果"
    assert mock_execute.call_count == 2
