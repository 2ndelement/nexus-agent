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


class SSEToolCall(BaseModel):
    """工具调用事件"""

    type: Literal["tool_call"] = "tool_call"
    tool_call_id: Optional[str] = None
    tool_name: str
    tool_args: dict = {}
    status: Literal["start", "complete", "error"] = "start"
    result: Optional[str] = None
    error: Optional[str] = None


class SSEMedia(BaseModel):
    """多媒体消息事件（V5 新增）

    用于 Agent 返回图片、视频、音频等多媒体内容。
    media_type: image | video | audio | file
    """

    type: Literal["media"] = "media"
    media_type: Literal["image", "video", "audio", "file"]
    url: str = Field(..., description="媒体文件 URL（MinIO/S3）")
    mime_type: str = Field(..., description="MIME 类型，如 image/png, video/mp4")
    filename: Optional[str] = Field(None, description="原始文件名")
    size: Optional[int] = Field(None, description="文件大小（字节）")
    width: Optional[int] = Field(None, description="图片/视频宽度")
    height: Optional[int] = Field(None, description="图片/视频高度")
    duration: Optional[float] = Field(None, description="音频/视频时长（秒）")
    thumbnail: Optional[str] = Field(None, description="视频缩略图 URL")


class SSEThinking(BaseModel):
    """思考过程事件（V5 新增）

    用于 MiniMax 等模型的思考过程输出。
    思考内容会显示在可折叠的独立区块中。
    """

    type: Literal["thinking"] = "thinking"
    content: str = Field(..., description="思考过程内容")


class SSEFollowupPending(BaseModel):
    """Follow-up 等待事件（V5 新增）

    当用户发送 follow-up 消息后，通知前端消息正在等待注入。
    """

    type: Literal["followup_pending"] = "followup_pending"
    followup_id: str = Field(..., description="Follow-up 消息 ID")
    content: str = Field(..., description="Follow-up 消息内容")


class SSEFollowupInjected(BaseModel):
    """Follow-up 注入事件（V5 新增）

    当 follow-up 消息被注入到工具结果中时，通知前端。
    """

    type: Literal["followup_injected"] = "followup_injected"
    followup_id: str = Field(..., description="已注入的 Follow-up 消息 ID")
    content: Optional[str] = Field(None, description="Follow-up 消息内容")
    injected_tool: Optional[str] = Field(None, description="注入到的工具名称")


class SSEContextStats(BaseModel):
    """上下文统计事件

    定期发送当前上下文长度和压缩状态，用于前端显示。
    """

    type: Literal["context_stats"] = "context_stats"
    token_count: int = Field(..., description="当前上下文 token 数量")
    max_context: int = Field(..., description="最大上下文 token 数")
    compressed: bool = Field(False, description="本次是否发生了压缩")
    timestamp: Optional[float] = Field(None, description="事件时间戳")
    read_tokens: int = Field(0, description="本轮 LLM 读取上下文 token 数")
    write_tokens: int = Field(0, description="本轮 assistant 输出 token 数")
    message_tokens: int = Field(0, description="当前 assistant 消息 token 数")


# ═══════════════════════════════════════════════════════════════════ 请求 ═══════════════════════════════════════════════════════════════════

class FollowupRequest(BaseModel):
    """POST /api/v1/agent/followup 请求体"""

    conversation_id: str = Field(..., description="会话 ID")
    content: str = Field(..., min_length=1, description="Follow-up 消息内容")


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
