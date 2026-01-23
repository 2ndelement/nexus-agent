"""
app/api/v1/chat.py — SSE 流式对话接口

POST /api/v1/agent/chat/stream
Request Headers:
    X-Tenant-Id: <tenant_id>   (必须，来自 Java Gateway 注入，不允许用户自填)
    X-User-Id: <user_id>       (必须)
    X-Conv-Id: <conv_id>       (必须)
Request Body: { "message": "..." }
Response: text/event-stream

SSE 事件格式：
    data: {"type": "chunk", "content": "..."}
    data: {"type": "done", "conversation_id": "..."}
    data: {"type": "error", "message": "..."}

POST /api/v1/agent/chat (非流式)
    用于 QQ 机器人等不需要流式输出的场景
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.agent.graph import astream_agent, build_graph, invoke_agent
from app.checkpointer import get_mysql_checkpointer
from app.schemas import ChatRequest, ChatRequestNonStream, ChatResponse, SSEChunk, SSEDone, SSEError

logger = logging.getLogger(__name__)

router = APIRouter()


def _sse_data(obj) -> str:
    """将 Pydantic model 序列化为 SSE data 字符串。"""
    return obj.model_dump_json()


async def _chat_event_generator(
    tenant_id: str,
    user_id: str,
    conversation_id: str,
    message: str,
) -> AsyncIterator[dict]:
    """
    SSE 事件生成器。

    异常时发送 error 事件而非直接断连（符合 Code Review 检查清单）。
    """
    try:
        async with get_mysql_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
            async for token in astream_agent(
                graph=graph,
                tenant_id=tenant_id,
                user_id=user_id,
                conversation_id=conversation_id,
                message=message,
            ):
                yield {"data": _sse_data(SSEChunk(content=token))}

        # 流式结束事件
        yield {"data": _sse_data(SSEDone(conversation_id=conversation_id))}

    except Exception as exc:
        logger.exception(
            "Agent 执行异常: tenant=%s, conv=%s", tenant_id, conversation_id
        )
        yield {"data": _sse_data(SSEError(message=str(exc)))}


@router.post("/chat/stream")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    x_user_id: str = Header(..., alias="X-User-Id"),
    x_conv_id: str = Header(..., alias="X-Conv-Id"),
):
    """
    SSE 流式对话接口。

    所有租户信息必须从 Header 获取（由 Java Gateway 注入），
    严禁从请求体或查询参数获取 tenant_id。
    """
    # message 已由 Pydantic min_length=1 校验，此处无需二次检查
    logger.info(
        "chat_stream: tenant=%s, user=%s, conv=%s",
        x_tenant_id,
        x_user_id,
        x_conv_id,
    )

    return EventSourceResponse(
        _chat_event_generator(
            tenant_id=x_tenant_id,
            user_id=x_user_id,
            conversation_id=x_conv_id,
            message=body.message,
        ),
        media_type="text/event-stream",
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_non_stream(
    request: Request,
    body: ChatRequestNonStream,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    x_user_id: str = Header(..., alias="X-User-Id"),
    x_conv_id: str = Header(..., alias="X-Conv-Id"),
):
    """
    非流式对话接口（用于 QQ 机器人等场景）。

    支持从 Header 或 Body 获取租户/用户/会话信息，
    Body 中的值优先级高于 Header。
    """
    # 使用 Body 中的值覆盖 Header（如果提供）
    tenant_id = body.tenant_id or x_tenant_id
    user_id = body.user_id or x_user_id
    conversation_id = body.conversation_id or x_conv_id

    logger.info(
        "chat_non_stream: tenant=%s, user=%s, conv=%s",
        tenant_id,
        user_id,
        conversation_id,
    )

    try:
        async with get_mysql_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
            result = await invoke_agent(
                graph=graph,
                tenant_id=tenant_id,
                user_id=user_id,
                conversation_id=conversation_id,
                message=body.message,
            )

        return ChatResponse(
            conversation_id=conversation_id,
            content=result,
        )

    except Exception as exc:
        logger.exception(
            "Agent 执行异常: tenant=%s, conv=%s", tenant_id, conversation_id
        )
        raise HTTPException(status_code=500, detail=str(exc))
