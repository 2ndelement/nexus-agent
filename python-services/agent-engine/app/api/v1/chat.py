"""
app/api/v1/chat.py — SSE 流式对话接口

POST /api/v1/agent/chat/stream
Request Headers:
    X-Tenant-Id: <tenant_id>   (必须，来自 Java Gateway 注入)
    X-User-Id: <user_id>       (必须)
    X-Conv-Id: <conv_id>       (必须)
Request Body: { "message": "..." }
Response: text/event-stream

SSE 事件格式：
    data: {"type": "chunk", "content": "..."}
    data: {"type": "done", "conversation_id": "..."}
    data: {"type": "error", "message": "..."}
    data: {"type": "stopped", "conversation_id": "..."}

POST /api/v1/agent/chat (非流式)
    用于 QQ 机器人等场景
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.agent.graph import astream_agent, build_graph, invoke_agent
from app.control.session_manager import get_session_manager, ConversationStatus
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
    SSE 事件生成器
    """
    from app.control.session_manager import get_session_manager
    from app.control.interrupt_controller import get_interrupt_controller
    
    session_mgr = await get_session_manager()
    interrupt_ctrl = await get_interrupt_controller()
    
    # 设置状态为运行中
    await session_mgr.set_running(conversation_id)
    
    try:
        async with get_mysql_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
            
            # 流式生成
            async for token in astream_agent(
                graph=graph,
                tenant_id=tenant_id,
                user_id=user_id,
                conversation_id=conversation_id,
                message=message,
            ):
                # 检查是否被中断
                if await interrupt_ctrl.check_interrupted(conversation_id):
                    signal = await interrupt_ctrl.wait_for_signal(conversation_id, timeout=0.1)
                    if signal:
                        if signal.action == "stop":
                            logger.info(f"[Chat] 对话被停止: {conversation_id}")
                            yield {"data": json.dumps({
                                "type": "stopped",
                                "conversation_id": conversation_id
                            })}
                            await session_mgr.set_stopped(conversation_id)
                            return
                
                yield {"data": _sse_data(SSEChunk(content=token))}

        # 流式结束事件
        yield {"data": _sse_data(SSEDone(conversation_id=conversation_id))}
        await session_mgr.set_completed(conversation_id)

    except InterruptedError as exc:
        logger.info(f"[Chat] Agent 被中断: {conversation_id} - {exc}")
        yield {"data": _sse_data(SSEError(message="Agent interrupted"))}
        await session_mgr.set_paused(conversation_id)
        
    except Exception as exc:
        logger.exception(f"[Chat] Agent 执行异常: tenant={tenant_id}, conv={conversation_id}")
        yield {"data": _sse_data(SSEError(message=str(exc)))}
        await session_mgr.set_stopped(conversation_id)


@router.post("/chat/stream")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    x_user_id: str = Header(..., alias="X-User-Id"),
    x_conv_id: str = Header(..., alias="X-Conv-Id"),
):
    """
    SSE 流式对话接口
    """
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
    非流式对话接口（用于 QQ 机器人等场景）
    """
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
        logger.exception(f"[Chat] Agent 执行异常: tenant={tenant_id}, conv={conversation_id}")
        raise HTTPException(status_code=500, detail=str(exc))
