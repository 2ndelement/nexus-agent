"""
app/schemas.py — Pydantic v2 请求/响应模型
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ─────────────────────────── 请求 ───────────────────────────

class ChatRequest(BaseModel):
    """POST /api/v1/agent/chat/stream 请求体"""

    message: str = Field(..., min_length=1, description="用户消息内容，不能为空")


# ─────────────────────────── SSE 事件 ───────────────────────────

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


# ─────────────────────────── 健康检查 ───────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "agent-engine"
