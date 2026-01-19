"""
app/agent/nodes.py — LangGraph 图节点函数

节点列表：
  1. call_llm_node   — 调用 LLM，可能返回 tool_calls
  2. tool_call_node  — 执行工具调用，将结果追加到 messages
  3. should_continue  — 条件路由：有 tool_calls → 工具节点，无 → 结束
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal

import httpx
from langchain_core.messages import AIMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.agent.state import AgentState
from app.config import settings

logger = logging.getLogger(__name__)

# ─────────────────── 工具定义（从 tool-registry 获取） ───────────────────

# 内置工具的 OpenAI function schema
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


# ─────────────────── 工具执行 ───────────────────

async def _execute_tool(tool_name: str, arguments: dict) -> str:
    """
    通过 tool-registry HTTP 接口执行工具。
    
    tool-registry 提供 POST /api/tools/execute:
    {
        "name": "calculator",
        "parameters": {"expression": "2+3"}
    }
    """
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
            # tool-registry 返回 {"code": 200, "data": {"result": "..."}}
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


# ─────────────────── LLM 构建 ───────────────────

def _build_llm() -> ChatOpenAI:
    """构建绑定了工具的 LLM 实例。"""
    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=settings.llm_temperature,
        streaming=True,
    )
    # 绑定工具定义，让 LLM 知道可用工具
    return llm.bind_tools(BUILTIN_TOOLS)


# ─────────────────── 节点函数 ───────────────────

async def call_llm_node(state: AgentState) -> dict:
    """
    LLM 调用节点。
    
    调用 LLM，LLM 可能返回：
    - 普通文本回复 → 进入 END
    - tool_calls → 进入 tool_call_node
    """
    llm = _build_llm()
    messages = state["messages"]

    logger.debug(
        "call_llm_node: tenant=%s, conv=%s, history_len=%d",
        state.get("tenant_id"),
        state.get("conversation_id"),
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
    工具执行节点。
    
    从最后一条 AIMessage 中提取 tool_calls，
    逐个执行并将结果作为 ToolMessage 追加到 messages。
    """
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

        result = await _execute_tool(tool_name, tool_args)

        tool_messages.append(
            ToolMessage(
                content=result,
                tool_call_id=tool_id,
            )
        )

    return {"messages": tool_messages}


# ─────────────────── 条件路由 ───────────────────

def should_continue(state: AgentState) -> Literal["tool_call", "end"]:
    """
    条件路由函数：
    - LLM 返回了 tool_calls → 进入 "tool_call" 节点
    - LLM 返回普通文本 → 进入 "end"
    """
    messages = state["messages"]
    
    # 检查最后一条 AIMessage
    last_msg = messages[-1] if messages else None
    
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        return "tool_call"
    
    return "end"
