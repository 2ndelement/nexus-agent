"""
app/api/v1/chat.py — SSE 流式对话接口

POST /api/v1/agent/chat/stream
POST /api/v1/agent/chat
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.agent.graph import astream_agent, build_graph, invoke_agent
from app.checkpointer import get_mysql_checkpointer
from app.client.session_client import get_session_client, MessageRole
from app.control.interrupt_controller import get_interrupt_controller
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
    """
    session_client = get_session_client()
    interrupt_ctrl = await get_interrupt_controller()
    
    # 1. 保存用户消息
    await session_client.add_user_message(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        content=message,
    )

    # 2. 构建初始状态
    from langchain_core.messages import HumanMessage
    from app.agent.state import AgentState
    
    input_state: AgentState = {
        "messages": [HumanMessage(content=message)],
        "tenant_id": tenant_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
    }
    
    # 3. 执行 Agent
    try:
        async with get_mysql_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
            
            # 收集完整回复
            full_response = ""
            
            async for token in astream_agent(
                graph=graph,
                tenant_id=tenant_id,
                user_id=user_id,
                conversation_id=conversation_id,
                message=message,
            ):
                # 检查是否被中断
                if interrupt_ctrl.is_stopped(conversation_id):
                    logger.info(f"[Chat] 对话被停止: {conversation_id}")
                    yield {"data": _sse_data(SSEError(message="User stopped"))}
                    interrupt_ctrl.clear(conversation_id)
                    return
                
                full_response += token
                yield {"data": _sse_data(SSEChunk(content=token))}

        # 4. 保存 AI 回复
        if full_response:
            await session_client.add_assistant_message(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                content=full_response,
            )

        # 5. 发送完成事件
        yield {"data": _sse_data(SSEDone(conversation_id=conversation_id))}

    except Exception as exc:
        logger.exception(f"[Chat] Agent 执行异常: tenant={tenant_id}, conv={conversation_id}")
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
    非流式对话接口（用于 QQ 机器人等场景）。
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
        # 保存用户消息
        session_client = get_session_client()
        await session_client.add_user_message(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            content=body.message,
        )

        # 执行 Agent
        async with get_mysql_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
            result = await invoke_agent(
                graph=graph,
                tenant_id=tenant_id,
                user_id=user_id,
                conversation_id=conversation_id,
                message=body.message,
            )

        # 保存 AI 回复
        await session_client.add_assistant_message(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            content=result,
        )

        return ChatResponse(
            conversation_id=conversation_id,
            content=result,
        )

    except Exception as exc:
        logger.exception(f"[Chat] Agent 执行异常: tenant={tenant_id}, conv={conversation_id}")
        raise HTTPException(status_code=500, detail=str(exc))
