"""
app/core/router.py — 多模型路由逻辑

职责：
1. 根据请求的 model 字段解析出对应的 ProviderConfig
2. 构建 openai.AsyncOpenAI 客户端（带连接池复用）
3. 执行非流式 / 流式 LLM 调用，返回标准化结果
"""
from __future__ import annotations

import asyncio
import logging
import threading
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


# ─── 客户端连接池（provider → client 缓存） ─────────────────────────────

class ClientPool:
    """
    Provider → AsyncOpenAI 客户端缓存池。

    - 每个 provider（以 base_url + api_key 为唯一标识）只创建一个客户端
    - AsyncOpenAI 底层使用 httpx.AsyncClient，自带连接池
    - 线程安全（使用 threading.Lock）
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clients: dict[str, openai.AsyncOpenAI] = {}

    def _make_key(self, provider: ProviderConfig) -> str:
        """生成 provider 唯一标识。"""
        return f"{provider.base_url}|{provider.api_key or 'no-key'}"

    def get(self, provider: ProviderConfig) -> openai.AsyncOpenAI:
        """获取或创建 AsyncOpenAI 客户端。"""
        key = self._make_key(provider)

        with self._lock:
            client = self._clients.get(key)
            if client is None:
                client = openai.AsyncOpenAI(
                    api_key=provider.api_key or "placeholder",
                    base_url=provider.base_url,
                    timeout=settings.llm_timeout,
                    max_retries=2,
                )
                self._clients[key] = client
                logger.info(
                    "ClientPool: 创建新客户端 base_url=%s (总数=%d)",
                    provider.base_url, len(self._clients),
                )
            return client

    async def close_all(self) -> None:
        """关闭所有缓存的客户端（优雅停机时调用）。"""
        with self._lock:
            for key, client in self._clients.items():
                try:
                    await client.close()
                except Exception as e:
                    logger.warning("关闭客户端失败: %s, %s", key, e)
            self._clients.clear()
            logger.info("ClientPool: 所有客户端已关闭")


# 全局单例
_client_pool = ClientPool()


def get_client_pool() -> ClientPool:
    """获取全局客户端池（用于 app shutdown 时 close）。"""
    return _client_pool


# ─── 参数构建 ─────────────────────────────────────────────────────────

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


# ─── 非流式调用 ───────────────────────────────────────────────────────

async def call_chat_completion(
    req: ChatCompletionRequest,
) -> ChatCompletionResponse:
    """
    非流式 LLM 调用。

    使用连接池复用客户端，不再每次新建。
    返回 ChatCompletionResponse（OpenAI 兼容格式）。
    """
    provider = settings.get_provider(req.model)
    client = _client_pool.get(provider)
    params = _build_params(req, provider)

    logger.info(
        "call_chat_completion: model=%s -> provider.model=%s base_url=%s",
        req.model, provider.model, provider.base_url,
    )

    try:
        raw = await asyncio.wait_for(
            client.chat.completions.create(**params, stream=False),
            timeout=settings.llm_timeout,
        )
    except asyncio.TimeoutError:
        raise RuntimeError(f"LLM 调用超时（{settings.llm_timeout}s）: model={req.model}")
    # 不再 close client — 由连接池管理生命周期

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
        model=req.model,
        choices=choices,
        usage=usage,
    )


# ─── 流式调用 ─────────────────────────────────────────────────────────

async def stream_chat_completion(
    req: ChatCompletionRequest,
) -> AsyncIterator[ChatCompletionStreamChunk]:
    """
    流式 LLM 调用。

    以异步生成器形式 yield ChatCompletionStreamChunk，
    调用方负责将其序列化为 SSE data 行。
    """
    provider = settings.get_provider(req.model)
    client = _client_pool.get(provider)
    params = _build_params(req, provider)

    logger.info(
        "stream_chat_completion: model=%s -> provider.model=%s base_url=%s",
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
    # 不再 close client — 由连接池管理
