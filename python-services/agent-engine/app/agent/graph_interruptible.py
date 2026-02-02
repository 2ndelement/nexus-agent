"""
app/agent/graph_interruptible.py — 支持中断的 LangGraph

基于 graph.py，增加中断支持：
1. 使用 nodes_interruptible.py 中的节点
2. 添加中断检查点
"""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from app.agent.nodes_interruptible import (
    call_llm_node,
    tool_call_node,
    should_continue,
    NodeInterrupt,
)
from app.agent.state import AgentState
from app.control.agent_controller import get_agent_controller

logger = logging.getLogger(__name__)


def build_interruptible_graph(checkpointer=None) -> Any:
    """
    编译并翻译支持中断的 LangGraph 图。

    图结构:
        START → call_llm → [should_continue] 
                                ├─ "tool_call" → tool_call_node → call_llm (循环)
                                └─ "end" → END

    每个节点执行前都会检查中断状态
    """
    builder = StateGraph(AgentState)

    # 节点（使用支持中断的版本）
    builder.add_node("call_llm", call_llm_node)
    builder.add_node("tool_call", tool_call_node)

    # 边
    builder.add_edge(START, "call_llm")
    
    # 条件路由
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
    """生成符合多租户隔离要求的 LangGraph config。"""
    thread_id = f"{tenant_id}:{conversation_id}"
    return {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "",
        }
    }


async def astream_agent_interruptible(
    graph: Any,
    tenant_id: str,
    user_id: str,
    conversation_id: str,
    message: str,
) -> AsyncIterator[tuple[str, str]]:
    """
    以流式方式运行 Agent，支持中断。

    Yields:
        tuple[str, str]: (event_type, data)
        - ("token", content): LLM token
        - ("interrupt", reason): 被中断
        - ("done", conversation_id): 完成
        - ("error", message): 错误

    Args:
        graph: 已编译的 LangGraph CompiledGraph。
        tenant_id: 租户 ID。
        user_id: 用户 ID。
        conversation_id: 会话 ID。
        message: 用户输入消息。

    Raises:
        NodeInterrupt: 当对话被用户中断时抛出
    """
    config = make_config(tenant_id, conversation_id)
    controller = get_agent_controller()

    input_state: dict = {
        "messages": [HumanMessage(content=message)],
        "tenant_id": tenant_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
    }

    logger.info(
        "astream_agent_interruptible start: thread_id=%s:%s, user=%s",
        tenant_id,
        conversation_id,
        user_id,
    )

    try:
        # 使用 astream_events 捕获流式 token
        async for event in graph.astream_events(input_state, config, version="v2"):
            kind = event.get("event")
            
            # 检查是否被中断
            if controller.is_interrupted(conversation_id):
                reason = controller.get_interrupt_reason(conversation_id)
                yield ("interrupt", reason.message if reason else "用户中断")
                return
            
            # on_chat_model_stream: LLM 流式输出 token
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield ("token", chunk.content)
            
            # on_chain_end: 节点执行完成
            elif kind == "on_chain_end":
                node_name = event.get("name", "")
                if node_name == "call_llm":
                    # LLM 调用完成，检查是否有待注入消息
                    pending_msg = controller.get_pending_message(conversation_id)
                    if pending_msg:
                        # 添加新消息到状态
                        input_state["messages"].append(HumanMessage(content=pending_msg))
                        logger.info(f"[Agent] 注入消息: {conversation_id}, msg={pending_msg[:50]}...")

        # 流式结束
        yield ("done", conversation_id)

    except NodeInterrupt as e:
        logger.info(f"[Agent] 对话被中断: {conversation_id}, reason={e}")
        yield ("interrupt", str(e))
        
    except Exception as e:
        logger.exception(f"[Agent] 执行异常: {conversation_id}")
        yield ("error", str(e))


async def invoke_agent_interruptible(
    graph: Any,
    tenant_id: str,
    user_id: str,
    conversation_id: str,
    message: str,
) -> str:
    """
    以非流式方式运行 Agent，支持中断。
    """
    config = make_config(tenant_id, conversation_id)
    controller = get_agent_controller()

    input_state: dict = {
        "messages": [HumanMessage(content=message)],
        "tenant_id": tenant_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
    }

    logger.info(
        "invoke_agent_interruptible start: thread_id=%s:%s, user=%s",
        tenant_id,
        conversation_id,
        user_id,
    )

    try:
        result = await graph.ainvoke(input_state, config)

        messages = result.get("messages", [])
        if messages:
            last_message = messages[-1]
            return last_message.content if hasattr(last_message, "content") else str(last_message)
        
        return ""
        
    except NodeInterrupt as e:
        logger.info(f"[Agent] 对话被中断: {conversation_id}")
        raise
        
    except Exception as e:
        logger.exception(f"[Agent] 执行异常: {conversation_id}")
        raise
