"""
app/agent/interrupt_nodes.py — 带中断支持的 Agent 节点

修改自 nodes.py，在每个节点执行前检查中断信号
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

from langchain_core.messages import AIMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.agent.state import AgentState
from app.config import settings

logger = logging.getLogger(__name__)


async def check_interrupt(conversation_id: str) -> bool:
    """
    检查是否被中断
    
    Args:
        conversation_id: 对话ID
    
    Returns:
        是否被中断
    """
    try:
        from app.control.interrupt_controller import get_interrupt_controller
        controller = await get_interrupt_controller()
        return await controller.check_interrupted(conversation_id)
    except Exception:
        return False


async def call_llm_node(state: AgentState) -> dict:
    """
    LLM 调用节点（带中断支持）
    """
    conversation_id = state.get("conversation_id", "")
    
    # 执行前检查中断
    if await check_interrupt(conversation_id):
        logger.info(f"[LLM Node] 检测到中断信号: {conversation_id}")
        raise InterruptedError(f"User interrupted: {conversation_id}")
    
    llm = _build_llm()
    messages = state["messages"]

    logger.debug(
        "call_llm_node: tenant=%s, conv=%s, history_len=%d",
        state.get("tenant_id"),
        conversation_id,
        len(messages),
    )

    try:
        response: AIMessage = await asyncio.wait_for(
            llm.ainvoke(messages),
            timeout=settings.llm_timeout,
        )
    except asyncio.TimeoutError as exc:
        raise TimeoutError(
            f"LLM 调用超时（>{settings.llm_timeout}s）"
        ) from exc

    return {"messages": [response]}


async def tool_call_node(state: AgentState) -> dict:
    """
    工具执行节点（带中断支持）
    """
    conversation_id = state.get("conversation_id", "")
    
    # 执行前检查中断
    if await check_interrupt(conversation_id):
        logger.info(f"[Tool Node] 检测到中断信号: {conversation_id}")
        raise InterruptedError(f"User interrupted: {conversation_id}")
    
    messages = state["messages"]
    
    # 找最后一条 AIMessage
    last_ai_msg = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            last_ai_msg = msg
            break

    if not last_ai_msg or not last_ai_msg.tool_calls:
        return {"messages": []}

    tool_messages = []
    for tool_call in last_ai_msg.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]

        logger.info("执行工具: name=%s, args=%s", tool_name, tool_args)

        # 检查中断
        if await check_interrupt(conversation_id):
            logger.info(f"[Tool Node] 工具执行中被中断: {conversation_id}")
            raise InterruptedError(f"User interrupted during tool: {tool_name}")

        result = await _execute_tool(tool_name, tool_args)

        tool_messages.append(
            ToolMessage(
                content=result,
                tool_call_id=tool_id,
            )
        )

    return {"messages": tool_messages}


def should_continue(state: AgentState) -> Literal["tool_call", "end"]:
    """
    条件路由函数
    """
    messages = state["messages"]
    
    last_msg = messages[-1] if messages else None
    
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        return "tool_call"
    
    return "end"


# 保留原有节点以兼容
async def call_llm_node_original(state: AgentState) -> dict:
    """原始 LLM 节点"""
    llm = _build_llm()
    messages = state["messages"]

    try:
        response: AIMessage = await asyncio.wait_for(
            llm.ainvoke(messages),
            timeout=settings.llm_timeout,
        )
    except asyncio.TimeoutError as exc:
        raise TimeoutError(
            f"LLM 调用超时（>{settings.llm_timeout}s）"
        ) from exc

    return {"messages": [response]}


async def tool_call_node_original(state: AgentState) -> dict:
    """原始工具节点"""
    messages = state["messages"]
    
    last_ai_msg = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            last_ai_msg = msg
            break

    if not last_ai_msg or not last_ai_msg.tool_calls:
        return {"messages": []}

    tool_messages = []
    for tool_call in last_ai_msg.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]

        result = await _execute_tool(tool_name, tool_args)

        tool_messages.append(
            ToolMessage(
                content=result,
                tool_call_id=tool_id,
            )
        )

    return {"messages": tool_messages}
