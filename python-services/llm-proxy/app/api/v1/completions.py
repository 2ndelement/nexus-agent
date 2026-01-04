"""
app/api/v1/completions.py — POST /v1/chat/completions

OpenAI 兼容的聊天补全接口，支持：
  - 非流式响应（stream: false）
  - 流式响应（stream: true），格式为 text/event-stream
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.core.router import call_chat_completion, stream_chat_completion
from app.core.token_stats import token_stats
from app.schemas import ChatCompletionRequest, ChatCompletionResponse, ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ─────────────────────────── 非流式 ───────────────────────────

@router.post(
    "/chat/completions",
    response_model=ChatCompletionResponse,
    summary="Chat Completions（OpenAI 兼容）",
)
async def chat_completions(req: ChatCompletionRequest) -> ChatCompletionResponse:
    """
    统一 LLM 调用入口。

    根据 `model` 字段路由到对应 Provider；支持 `stream: true` 流式输出。
    Token 用量自动统计并累加到全局计数器。
    """
    if req.stream:
        return await _handle_stream(req)  # type: ignore[return-value]
    return await _handle_non_stream(req)


async def _handle_non_stream(req: ChatCompletionRequest) -> ChatCompletionResponse:
    """处理非流式请求。"""
    logger.info("non-stream request: model=%s msgs=%d", req.model, len(req.messages))
    try:
        resp = await call_chat_completion(req)
    except Exception as exc:
        logger.exception("非流式 LLM 调用失败: model=%s", req.model)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ErrorResponse(
                error=ErrorDetail(message=str(exc), type="upstream_error")
            ).model_dump(),
        )

    # 统计 token
    await token_stats.record(
        model=req.model,
        prompt_tokens=resp.usage.prompt_tokens,
        completion_tokens=resp.usage.completion_tokens,
    )
    return resp


async def _handle_stream(req: ChatCompletionRequest) -> StreamingResponse:
    """处理流式请求，返回 text/event-stream 响应。"""
    logger.info("stream request: model=%s msgs=%d", req.model, len(req.messages))

    async def _event_generator():
        prompt_tokens = 0
        completion_tokens = 0
        try:
            async for chunk in stream_chat_completion(req):
                # 累计 token（流式结束 chunk 可能携带 usage）
                if chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens
                    completion_tokens = chunk.usage.completion_tokens

                # 统计 completion tokens：每个非空 delta content 估算
                for choice in chunk.choices:
                    if choice.delta.content:
                        completion_tokens += len(choice.delta.content.split())

                line = f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"
                yield line

        except Exception as exc:
            logger.exception("流式 LLM 调用失败: model=%s", req.model)
            error_line = (
                f"data: {json.dumps({'error': {'message': str(exc), 'type': 'upstream_error'}})}\n\n"
            )
            yield error_line
        finally:
            # 流结束后记录统计
            await token_stats.record(
                model=req.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
