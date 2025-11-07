"""
app/agent/state.py — AgentState TypedDict 定义
"""
from __future__ import annotations

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """
    LangGraph 图的状态定义。

    messages 使用 add_messages reducer：
    - 新消息追加到历史，不覆盖
    - 多租户隔离通过 thread_id = f"{tenant_id}:{conversation_id}" 实现
    """

    messages: Annotated[list[BaseMessage], add_messages]
    tenant_id: str
    user_id: str
    conversation_id: str
