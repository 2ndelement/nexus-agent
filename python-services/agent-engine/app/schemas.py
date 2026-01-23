"""
app/schemas.py — Pydantic v2 请求/响应模型
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════ 请求 ═══════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    """POST /api/v1/agent/chat/stream 请求体"""

    message: str = Field(..., min_length=1, description="用户消息内容，不能为空")


class ChatRequestNonStream(BaseModel):
    """POST /api/v1/agent/chat 请求体（非流式）"""

    message: str = Field(..., min_length=1, description="用户消息内容，不能为空")
    tenant_id: Optional[str] = Field(None, description="租户ID（可选，从Header读取则不需要）")
    user_id: Optional[str] = Field(None, description="用户ID（可选，从Header读取则不需要）")
    conversation_id: Optional[str] = Field(None, description="会话ID（可选，从Header读取则不需要）")


# ═══════════════════════════════════════════════════════════════════ SSE 事件 ═══════════════════════════════════════════════════════════════════

class SSEChunk(BaseModel):
    """流式文本块"""

    type: Literal["chunk"] = "chunk"
    content: str


class SSEDone(BaseModel):
    """流式结束"""

    type: Literal["done"] = "done"
    conversation_id: str


class SSEError(BaseModel):
    """流式错误"""

    type: Literal["error"] = "error"
    message: str


# ═══════════════════════════════════════════════════════════════════ 非流式响应 ═══════════════════════════════════════════════════════════════════

class ChatResponse(BaseModel):
    """POST /api/v1/agent/chat 响应体（非流式）"""

    conversation_id: str
    content: str
    message: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════ 健康检查 ═══════════════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "agent-engine"
