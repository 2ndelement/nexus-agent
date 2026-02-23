"""
app/agent/state.py — AgentState TypedDict 定义

V5 更新：
- 使用 owner_type + owner_id 替代 tenant_id
- owner_type: PERSONAL（个人空间）或 ORGANIZATION（组织空间）
- owner_id: 用户 ID 或组织 code
"""
from __future__ import annotations

from typing import Annotated, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """
    LangGraph 图的状态定义。

    messages 使用 add_messages reducer：
    - 新消息追加到历史，不覆盖
    - V5 多空间隔离通过 thread_id = f"{owner_type}:{owner_id}:{platform}:{bot_id}:{conversation_id}" 实现

    系统提示词：
    - system_prompt 从 agent_config 表获取
    - 在 call_llm_node 中作为 SystemMessage 注入
    """

    messages: Annotated[list[BaseMessage], add_messages]
    owner_type: str  # PERSONAL 或 ORGANIZATION
    owner_id: str  # 用户 ID 或组织 code
    platform: Optional[str]  # 平台类型：WEB, QQ, QQ_GROUP, QQ_GUILD, FEISHU 等
    bot_id: Optional[str]  # Bot ID
    user_id: str
    conversation_id: str
    agent_id: Optional[str]  # Agent 配置 ID
    system_prompt: Optional[str]  # 系统提示词（从 agent_config 表获取）
    model: Optional[str]  # 模型 ID（如 gpt-5-mini）
    temperature: Optional[float]  # 温度参数
    knowledge_base_ids: Optional[list[str]]  # Agent 绑定的知识库 ID 列表
    followup_injected: Optional[list[dict]]  # V5: 注入的 follow-up 信息列表
