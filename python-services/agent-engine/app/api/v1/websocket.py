"""
app/api/v1/websocket.py — WebSocket 接口（简化版）

支持：
- 发送消息并接收流式响应
- 随时发送 stop 停止对话
- 发送 followup 注入消息
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.agent.graph import build_graph, astream_agent
from app.checkpointer import get_mysql_checkpointer
from app.client.session_client import get_session_client, MessageRole
from app.control.interrupt_controller import get_interrupt_controller
from app.control.followup_queue import get_followup_queue, FollowupMessage
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/{conversation_id}")
async def agent_websocket(websocket: WebSocket):
    """
    Agent WebSocket 接口
    
    URL: /api/v1/agent/ws/{conversation_id}?tenant_id=xxx&user_id=xxx
    """
    await websocket.accept()
    
    # 获取参数
    conversation_id = websocket.path_params.get("conversation_id", "default")
    tenant_id = websocket.query_params.get("tenant_id", "default")
    user_id = websocket.query_params.get("user_id", "anonymous")
    
    session_client = get_session_client()
    interrupt_ctrl = await get_interrupt_controller()
    followup_queue = await get_followup_queue()
    
    logger.info(
        f"[WebSocket] 连接建立: conv={conversation_id}, "
        f"tenant={tenant_id}, user={user_id}"
    )
    
    # 发送连接成功消息
    await websocket.send_json({
        "type": "connected",
        "conversation_id": conversation_id,
    })
    
    current_task = None
    
    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "message")
                
                if msg_type == "message":
                    # 处理消息
                    content = msg.get("content", "").strip()
                    if not content:
                        await websocket.send_json({
                            "type": "error",
                            "message": "消息内容不能为空"
                        })
                        continue
                    
                    # 取消之前的任务
                    if current_task and not current_task.done():
                        current_task.cancel()
                    
                    # 启动新任务
                    current_task = asyncio.create_task(
                        _process_message(
                            websocket, conversation_id, tenant_id, user_id, content
                        )
                    )
                
                elif msg_type == "stop":
                    # 停止对话
                    logger.info(f"[WebSocket] 收到停止请求: {conversation_id}")
                    await interrupt_ctrl.stop(conversation_id)
                    
                    # 取消当前任务
                    if current_task and not current_task.done():
                        current_task.cancel()
                    
                    await websocket.send_json({
                        "type": "stopped",
                        "conversation_id": conversation_id
                    })
                
                elif msg_type == "followup":
                    # 添加 followup 到队列
                    content = msg.get("content", "").strip()
                    if content:
                        import uuid
                        followup = FollowupMessage(
                            followup_id=str(uuid.uuid4()),
                            conversation_id=conversation_id,
                            content=content,
                            created_at=asyncio.get_event_loop().time(),
                        )
                        await followup_queue.add(followup)
                        
                        await websocket.send_json({
                            "type": "followup_queued",
                            "followup_id": followup.followup_id
                        })
                
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"未知消息类型: {msg_type}"
                    })
            
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "JSON 格式错误"
                })
    
    except WebSocketDisconnect:
        logger.info(f"[WebSocket] 连接断开: {conversation_id}")
    except asyncio.CancelledError:
        logger.info(f"[WebSocket] 任务取消: {conversation_id}")
    except Exception as e:
        logger.exception(f"[WebSocket] 异常: {e}")
    finally:
        interrupt_ctrl.clear(conversation_id)
        logger.info(f"[WebSocket] 连接关闭: {conversation_id}")


async def _process_message(
    websocket: WebSocket,
    conversation_id: str,
    tenant_id: str,
    user_id: str,
    content: str,
):
    """处理消息"""
    session_client = get_session_client()
    interrupt_ctrl = await get_interrupt_controller()
    followup_queue = await get_followup_queue()
    
    # 保存用户消息
    await session_client.add_user_message(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        content=content,
    )
    
    # 发送确认
    await websocket.send_json({
        "type": "ack",
        "status": "processing"
    })
    
    # 收集完整回复
    full_response = ""
    
    try:
        async with get_mysql_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
            
            # 检查 followup 队列
            pending = await followup_queue.get_pending(conversation_id)
            if pending:
                # 注入 followup 到消息
                followup_contents = [f.content for f in pending]
                followup_prompt = "\n[用户插入了新消息]\n" + "\n".join(followup_contents)
                content = content + followup_prompt
                
                # 标记已注入
                for f in pending:
                    await followup_queue.mark_injected(conversation_id, f.followup_id)
            
            async for token in astream_agent(
                graph=graph,
                tenant_id=tenant_id,
                user_id=user_id,
                conversation_id=conversation_id,
                message=content,
            ):
                # 检查是否被停止
                if interrupt_ctrl.is_stopped(conversation_id):
                    await websocket.send_json({
                        "type": "stopped",
                        "conversation_id": conversation_id
                    })
                    return
                
                full_response += token
                await websocket.send_json({
                    "type": "reply",
                    "content": token
                })
        
        # 保存 AI 回复
        if full_response:
            await session_client.add_assistant_message(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                content=full_response,
            )
        
        # 发送完成
        await websocket.send_json({
            "type": "done",
            "conversation_id": conversation_id
        })
    
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception(f"处理消息异常: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
