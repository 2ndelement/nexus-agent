"""
app/core/router.py — 多模型路由逻辑

职责：
1. 根据请求的 model 字段解析出对应的 ProviderConfig
2. 构建 openai.AsyncOpenAI 客户端
3. 执行非流式 / 流式 LLM 调用，返回标准化结果
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import AsyncIterator

import openai

from app.config import ProviderConfig, settings
from app.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionStreamChunk,
    Choice,
    ChoiceMessage,
    DeltaMessage,
    StreamChoice,
    UsageInfo,
)

logger = logging.getLogger(__name__)


def _build_client(provider: ProviderConfig) -> openai.AsyncOpenAI:
    """为指定 provider 构建 AsyncOpenAI 客户端（每次调用新建，轻量无状态）。"""
    return openai.AsyncOpenAI(
        api_key=provider.api_key or "placeholder",  # 部分兼容接口不需要 key
        base_url=provider.base_url,
        timeout=settings.llm_timeout,
    )


def _build_params(req: ChatCompletionRequest, provider: ProviderConfig) -> dict:
    """
    从请求体构建发往上游的参数字典。
    - model 替换为 provider.model（防止客户端传入的 model 与上游不符）
    - 过滤 None 值，避免上游报错
    """
    params: dict = {
        "model": provider.model,
        "messages": [m.model_dump(exclude_none=True) for m in req.messages],
    }
    optional_fields = [
        "temperature", "top_p", "max_tokens", "n",
        "stop", "presence_penalty", "frequency_penalty", "user",
    ]
    for field in optional_fields:
        value = getattr(req, field, None)
        if value is not None:
            params[field] = value
    return params


async def call_chat_completion(
    req: ChatCompletionRequest,
) -> ChatCompletionResponse:
    """
    非流式 LLM 调用。

    返回 ChatCompletionResponse（OpenAI 兼容格式）。
    """
    provider = settings.get_provider(req.model)
    client = _build_client(provider)
    params = _build_params(req, provider)

    logger.info(
        "call_chat_completion: model=%s → provider.model=%s base_url=%s",
        req.model, provider.model, provider.base_url,
    )

    try:
        raw = await asyncio.wait_for(
            client.chat.completions.create(**params, stream=False),
            timeout=settings.llm_timeout,
        )
    except asyncio.TimeoutError:
        raise RuntimeError(f"LLM 调用超时（{settings.llm_timeout}s）: model={req.model}")
    finally:
        await client.close()

    # 转换为内部 schema
    choices = [
        Choice(
            index=c.index,
            message=ChoiceMessage(
                role=c.message.role,
                content=c.message.content,
            ),
            finish_reason=c.finish_reason,
        )
        for c in raw.choices
    ]

    usage = UsageInfo(
        prompt_tokens=raw.usage.prompt_tokens if raw.usage else 0,
        completion_tokens=raw.usage.completion_tokens if raw.usage else 0,
        total_tokens=raw.usage.total_tokens if raw.usage else 0,
    )

    return ChatCompletionResponse(
        id=raw.id or f"chatcmpl-{uuid.uuid4().hex[:12]}",
        created=raw.created or int(time.time()),
        model=req.model,          # 返回给客户端的 model 保持请求中的名称
        choices=choices,
        usage=usage,
    )


async def stream_chat_completion(
    req: ChatCompletionRequest,
) -> AsyncIterator[ChatCompletionStreamChunk]:
    """
    流式 LLM 调用。

    以异步生成器形式 yield ChatCompletionStreamChunk，
    调用方负责将其序列化为 SSE data 行。
    """
    provider = settings.get_provider(req.model)
    client = _build_client(provider)
    params = _build_params(req, provider)

    logger.info(
        "stream_chat_completion: model=%s → provider.model=%s base_url=%s",
        req.model, provider.model, provider.base_url,
    )

    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())

    try:
        stream = await client.chat.completions.create(**params, stream=True)
        async for raw_chunk in stream:
            if not raw_chunk.choices:
                continue
            rc = raw_chunk.choices[0]
            delta = DeltaMessage(
                role=rc.delta.role if rc.delta.role else None,
                content=rc.delta.content if rc.delta.content else None,
            )
            yield ChatCompletionStreamChunk(
                id=chunk_id,
                created=created,
                model=req.model,
                choices=[
                    StreamChoice(
                        index=rc.index,
                        delta=delta,
                        finish_reason=rc.finish_reason,
                    )
                ],
            )
    except asyncio.TimeoutError:
        raise RuntimeError(f"LLM 流式调用超时（{settings.llm_timeout}s）: model={req.model}")
    finally:
        await client.close()
