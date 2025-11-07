"""
app/agent/nodes.py — LangGraph 图节点函数

每个节点接收 AgentState，返回局部更新字典（LangGraph 自动 merge）。
"""
from __future__ import annotations

import asyncio
import logging

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from app.agent.state import AgentState
from app.config import settings

logger = logging.getLogger(__name__)


def _build_llm() -> ChatOpenAI:
    """构建 LLM 实例（每次调用构建，避免全局共享状态）。"""
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=settings.llm_temperature,
        streaming=True,
    )


async def call_llm_node(state: AgentState) -> dict:
    """
    LLM 调用节点。

    从 state.messages 获取对话历史，调用 LLM 并返回 AI 回复。
    包含超时保护（settings.llm_timeout 秒）。
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
