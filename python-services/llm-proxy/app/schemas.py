"""
app/schemas.py — Pydantic v2 请求/响应模型（OpenAI 协议兼容）

严格对齐 OpenAI Chat Completions API：
  https://platform.openai.com/docs/api-reference/chat
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ─────────────────────────── 请求模型 ───────────────────────────

class ChatMessage(BaseModel):
    """单条对话消息。"""
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[Any] | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[Any] | None = None


class ChatCompletionRequest(BaseModel):
    """
    POST /v1/chat/completions 请求体。

    完全兼容 OpenAI Chat Completions API，支持代理透传所有字段。
    """
    model: str = Field(
        default="MiniMax-M2.5-highspeed",
        description="目标模型名称，用于路由到对应 Provider",
    )
    messages: list[ChatMessage] = Field(..., min_length=1)
    stream: bool = False
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    max_tokens: int | None = Field(default=None, gt=0)
    n: int | None = Field(default=None, ge=1)
    stop: str | list[str] | None = None
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    user: str | None = None
    # 允许透传其他字段给上游
    model_config = {"extra": "allow"}


# ─────────────────────────── 响应模型 ───────────────────────────

class UsageInfo(BaseModel):
    """Token 用量信息。"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChoiceMessage(BaseModel):
    """非流式响应中 choice 的 message 字段。"""
    role: str = "assistant"
    content: str | None = None
    tool_calls: list[Any] | None = None


class Choice(BaseModel):
    """非流式响应中的单个 choice。"""
    index: int = 0
    message: ChoiceMessage
    finish_reason: str | None = None
    logprobs: Any | None = None


class ChatCompletionResponse(BaseModel):
    """POST /v1/chat/completions 非流式响应体（OpenAI 兼容）。"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: UsageInfo
    system_fingerprint: str | None = None


# ─────────────────── 流式响应 Delta 模型 ───────────────────────

class DeltaMessage(BaseModel):
    """流式 chunk 中 delta 字段。"""
    role: str | None = None
    content: str | None = None
    tool_calls: list[Any] | None = None


class StreamChoice(BaseModel):
    """流式响应中的单个 choice。"""
    index: int = 0
    delta: DeltaMessage
    finish_reason: str | None = None
    logprobs: Any | None = None


class ChatCompletionStreamChunk(BaseModel):
    """流式 SSE data 的 JSON 体（OpenAI 兼容）。"""
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[StreamChoice]
    usage: UsageInfo | None = None


# ─────────────────────────── 统计 ───────────────────────────────

class ModelStats(BaseModel):
    """单个 model 的统计数据。"""
    requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class StatsResponse(BaseModel):
    """GET /v1/stats 响应体。"""
    total_requests: int = 0
    total_tokens: int = 0
    by_model: dict[str, ModelStats] = Field(default_factory=dict)


# ─────────────────────────── 健康检查 ────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "llm-proxy"


# ─────────────────────────── 错误 ────────────────────────────────

class ErrorDetail(BaseModel):
    message: str
    type: str = "proxy_error"
    code: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
