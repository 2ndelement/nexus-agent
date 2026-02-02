"""
app/agent/nodes_interruptible.py — 支持中断的 LangGraph 节点

这些节点在执行前会检查中断状态，
如果被中断则抛出 NodeInterrupt 异常。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Literal

from langchain_core.messages import AIMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.agent.state import AgentState
from app.control.agent_controller import get_agent_controller
from app.config import settings

logger = logging.getLogger(__name__)


async def check_interrupt(conversation_id: str):
    """
    检查是否被中断
    
    如果被中断，抛出 NodeInterrupt 异常
    """
    controller = get_agent_controller()
    
    if controller.is_interrupted(conversation_id):
        # 清除中断状态（只中断一次）
        reason = controller.get_interrupt_reason(conversation_id)
        logger.info(f"[Nodes] 检测到中断: {conversation_id}, reason={reason}")
        raise NodeInterrupt(f"Conversation {conversation_id} interrupted")


class NodeInterrupt(Exception):
    """节点中断异常"""
    pass


# 内置工具定义（与 nodes.py 相同）
BUILTIN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "执行数学表达式计算。支持 +, -, *, /, **, sqrt, log 等",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '2 + 3 * 4'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜索互联网获取实时信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_execute",
            "description": "在隔离沙箱中执行 Python 或 Bash 代码并返回结果。适用于数据分析、计算、文件处理等任务。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "要执行的代码",
                    },
                    "language": {
                        "type": "string",
                        "enum": ["python", "bash"],
                        "default": "python",
                        "description": "代码语言",
                    },
                    "timeout": {
                        "type": "integer",
                        "default": 30,
                        "description": "超时秒数",
                    },
                },
                "required": ["code"],
            },
        },
    },
]


def _build_llm() -> ChatOpenAI:
    """构建绑定了工具的 LLM 实例。"""
    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=settings.llm_temperature,
        streaming=True,
    )
    return llm.bind_tools(BUILTIN_TOOLS)


async def call_llm_node(state: AgentState) -> dict:
    """
    LLM 调用节点（支持中断）
    
    在调用 LLM 前检查是否被中断
    """
    conversation_id = state.get("conversation_id", "")
    
    # 检查中断
    await check_interrupt(conversation_id)
    
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
    工具执行节点（支持中断）
    
    在执行工具前检查是否被中断
    """
    conversation_id = state.get("conversation_id", "")
    
    # 检查中断
    await check_interrupt(conversation_id)
    
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
        # 检查中断
        await check_interrupt(conversation_id)
        
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]

        logger.info("执行工具: name=%s, args=%s", tool_name, tool_args)

        result = await _execute_tool(tool_name, tool_args)

        tool_messages.append(
            ToolMessage(
                content=result,
                tool_call_id=tool_id,
            )
        )

    return {"messages": tool_messages}


async def _execute_tool(tool_name: str, arguments: dict) -> str:
    """通过 tool-registry HTTP 接口执行工具。"""
    import httpx
    
    url = f"{settings.tool_registry_url}/api/tools/execute"
    payload = {
        "name": tool_name,
        "parameters": arguments,
    }
    
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == 200:
                result = data.get("data", {}).get("result", "")
                return str(result)
            else:
                return f"工具执行失败: {data.get('msg', 'unknown error')}"
    except httpx.TimeoutException:
        return f"工具 {tool_name} 执行超时"
    except Exception as e:
        logger.exception("工具执行异常: %s", tool_name)
        return f"工具执行异常: {str(e)}"


def should_continue(state: AgentState) -> Literal["tool_call", "end"]:
    """
    条件路由函数：
    - LLM 返回了 tool_calls → 进入 "tool_call" 节点
    - LLM 返回普通文本 → 进入 "end"
    """
    messages = state["messages"]
    
    last_msg = messages[-1] if messages else None
    
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        return "tool_call"
    
    return "end"
