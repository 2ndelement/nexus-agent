"""
app/agent/nodes.py — LangGraph 图节点函数

节点列表：
  1. call_llm_node   — 调用 LLM，可能返回 tool_calls
  2. tool_call_node  — 执行工具调用，将结果追加到 messages
  3. should_continue — 条件路由：有 tool_calls → 工具节点，无 → 结束
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.agent.state import AgentState
from app.config import settings

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════ 内置工具定义 ═══════════════════════════════════════════════════════════════

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
                        "default": 60,
                        "minimum": 1,
                        "maximum": 3600,
                        "description": "超时秒数（1-3600）",
                    },
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_browser",
            "description": "浏览和管理 Skill 技能文件。列出技能、读取 SKILL.md、读取技能文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "read", "read_file", "tree"],
                        "description": "操作类型",
                    },
                    "skill_name": {
                        "type": "string",
                        "description": "技能名称",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "文件路径",
                    },
                },
                "required": ["action"],
            },
        },
    },
]

# ═══════════════════════════════════════════════════════════════ 工具执行 ═══════════════════════════════════════════════════════════════

async def _execute_tool(tool_name: str, arguments: dict) -> str:
    """执行工具"""
    if tool_name == "skill_browser":
        return await _execute_skill_browser(arguments)
    elif tool_name == "calculator":
        return _execute_calculator(arguments)
    elif tool_name == "sandbox_execute":
        return await _execute_sandbox(arguments)
    elif tool_name == "web_search":
        return await _execute_search(arguments)
    else:
        return f"未知工具: {tool_name}"


async def _execute_skill_browser(arguments: dict) -> str:
    """执行 Skill 浏览器工具"""
    try:
        from app.tools.skill_browser import skill_browser as skill_browser_func
        result = await skill_browser_func(
            action=arguments.get("action"),
            tenant_id=arguments.get("tenant_id", ""),
            skill_name=arguments.get("skill_name"),
            file_path=arguments.get("file_path"),
        )
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"skill_browser 执行失败: {e}")
        return f"skill_browser 执行失败: {e}"


def _execute_calculator(arguments: dict) -> str:
    """计算器"""
    try:
        expression = arguments.get("expression", "")
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"计算错误: {e}"


async def _execute_sandbox(arguments: dict) -> str:
    """沙箱执行"""
    import httpx
    url = f"{settings.sandbox_url}/execute"
    try:
        async with httpx.AsyncClient(timeout=arguments.get("timeout", 60) as client:
        resp = await client.post(url, json={
            "code": arguments.get("code"),
            "language": arguments.get("language", "python"),
            "timeout": arguments.get("timeout", 60),
        })
        if resp.status_code == 200:
            return resp.text
        else:
            return f"执行失败: {resp.status_code}"
    except Exception as e:
        return f"执行失败: {e}"


async def _execute_search(arguments: dict) -> str:
    """网络搜索"""
    return "搜索功能开发中"


# ═══════════════════════════════════════════════════════════════ 节点函数 ═══════════════════════════════════════════════════════════════

async def call_llm_node(state: AgentState) -> dict:
    """LLM 调用节点。"""
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=settings.llm_temperature,
        streaming=True,
    ).bind_tools(BUILTIN_TOOLS)
    
    messages = state["messages"]
    
    try:
        response = await asyncio.wait_for(
            llm.ainvoke(messages),
            timeout=settings.llm_timeout,
        )
    except asyncio.TimeoutError:
        return {"messages": [AIMessage(content="请求超时")]}
    
    return {"messages": [response]}


async def tool_call_node(state: AgentState) -> dict:
    """工具执行节点。"""
    messages = state["messages"]
    
    last_ai_msg = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            last_ai_msg = msg
            break
    
    if not last_ai_msg or not last_ai_msg.tool_calls:
        return {"messages": []}
    
    tool_messages = []
    for tool_call in last_ai_msg.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]
        
        logger.info("执行工具: %s", tool_name)
        
        result = await _execute_tool(tool_name, tool_args)
        
        tool_messages.append(ToolMessage(
            content=result,
            tool_call_id=tool_id,
        ))
    
    return {"messages": tool_messages}


def should_continue(state: AgentState) -> Literal["tool_call", "end"]:
    """条件路由"""
    messages = state["messages"]
    last_msg = messages[-1] if messages else None
    
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        return "tool_call"
    return "end"
