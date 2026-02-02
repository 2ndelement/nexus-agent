"""
app/agent/interrupt_graph.py — 带中断支持的 LangGraph

基于 graph.py，添加中断支持
"""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from app.agent.state import AgentState
from app.agent.nodes import call_llm_node_original, tool_call_node_original, should_continue

logger = logging.getLogger(__name__)


def build_interrupted_graph(checkpointer=None) -> Any:
    """
    构建带中断支持的 LangGraph
    
    使用带中断检查的节点版本
    """
    from app.agent.interrupt_nodes import call_llm_node, tool_call_node
    
    builder = StateGraph(AgentState)

    # 节点（使用带中断支持的版本）
    builder.add_node("call_llm", call_llm_node)
    builder.add_node("tool_call", tool_call_node)

    # 边
    builder.add_edge(START, "call_llm")
    
    builder.add_conditional_edges(
        "call_llm",
        should_continue,
        {
            "tool_call": "tool_call",
            "end": END,
        },
    )
    
    builder.add_edge("tool_call", "call_llm")

    return builder.compile(checkpointer=checkpointer)


def build_normal_graph(checkpointer=None) -> Any:
    """
    构建普通 LangGraph（不带中断）
    """
    builder = StateGraph(AgentState)

    builder.add_node("call_llm", call_llm_node_original)
    builder.add_node("tool_call", tool_call_node_original)

    builder.add_edge(START, "call_llm")
    
    builder.add_conditional_edges(
        "call_llm",
        should_continue,
        {
            "tool_call": "tool_call",
            "end": END,
        },
    )
    
    builder.add_edge("tool_call", "call_llm")

    return builder.compile(checkpointer=checkpointer)


def make_config(tenant_id: str, conversation_id: str) -> dict:
    """生成配置"""
    thread_id = f"{tenant_id}:{conversation_id}"
    return {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "",
        }
    }


async def astream_agent_with_interrupt(
    graph: Any,
    tenant_id: str,
    user_id: str,
    conversation_id: str,
    message: str,
) -> AsyncIterator[str]:
    """
    带中断支持的流式 Agent
    
    Args:
        graph: 已编译的 LangGraph
        tenant_id: 租户ID
        user_id: 用户ID
        conversation_id: 会话ID
        message: 消息
    
    Yields:
        AI 回复 token
    """
    config = make_config(tenant_id, conversation_id)

    input_state: dict = {
        "messages": [HumanMessage(content=message)],
        "tenant_id": tenant_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
    }

    logger.info(
        "astream_agent_with_interrupt: thread_id=%s:%s",
        tenant_id,
        conversation_id,
    )

    try:
        async for event in graph.astream_events(input_state, config, version="v2"):
            kind = event.get("event")
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield chunk.content
    except InterruptedError as e:
        logger.info(f"Agent 被中断: {conversation_id} - {e}")
        raise
