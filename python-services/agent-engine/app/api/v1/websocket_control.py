"""
app/api/v1/websocket_control.py — WebSocket 控制接口

通过 WebSocket 支持前端中断控制

WebSocket 消息格式：

1. 发送消息：
{
    "type": "message",
    "content": "用户消息"
}

2. 停止对话：
{
    "type": "stop"
}

3. 接收响应：
{
    "type": "reply",
    "content": "AI回复内容"
}
{
    "type": "stopped",
    "conversation_id": "xxx"
}
{
    "type": "error",
    "message": "错误信息"
}
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
from app.control.session_manager import get_session_manager, ConversationStatus
from app.control.interrupt_controller import get_interrupt_controller

logger = logging.getLogger(__name__)

router = APIRouter()


class WebSocketConnection:
    """WebSocket 连接管理"""

    def __init__(self, websocket: WebSocket, conversation_id: str):
        self.websocket = websocket
        self.conversation_id = conversation_id
        self._running = True

    async def send_json(self, data: dict):
        """发送 JSON 消息"""
        if self.websocket.client_state == WebSocketState.CONNECTED:
            await self.websocket.send_json(data)

    async def send_text(self, data: str):
        """发送文本消息"""
        if self.websocket.client_state == WebSocketState.CONNECTED:
            await self.websocket.send_text(data)

    def is_active(self) -> bool:
        """检查连接是否活跃"""
        return self.websocket.client_state == WebSocketState.CONNECTED and self._running

    def stop(self):
        """停止连接"""
        self._running = False


@router.websocket("/ws/agent")
async def agent_websocket(websocket: WebSocket):
    """
    Agent WebSocket 接口
    
    支持：
    - 发送消息并接收流式响应
    - 随时发送 stop 停止对话
    """
    await websocket.accept()
    
    # 从 URL 参数获取会话信息
    conversation_id = websocket.path_params.get("conversation_id", "default")
    tenant_id = websocket.query_params.get("tenant_id", "default")
    user_id = websocket.query_params.get("user_id", "anonymous")
    
    connection = WebSocketConnection(websocket, conversation_id)
    session_mgr = await get_session_manager()
    interrupt_ctrl = await get_interrupt_controller()
    
    # 创建会话
    await session_mgr.create_conversation(conversation_id)
    
    logger.info(
        f"[WebSocket] 连接建立: conv={conversation_id}, "
        f"tenant={tenant_id}, user={user_id}"
    )
    
    # 发送连接成功消息
    await connection.send_json({
        "type": "connected",
        "conversation_id": conversation_id,
        "status": "idle"
    })
    
    try:
        while connection.is_active():
            # 接收消息
            data = await websocket.receive_text()
            
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "message")
                
                if msg_type == "message":
                    # 处理消息
                    content = msg.get("content", "").strip()
                    if not content:
                        await connection.send_json({
                            "type": "error",
                            "message": "消息内容不能为空"
                        })
                        continue
                    
                    # 设置状态为运行中
                    await session_mgr.set_running(conversation_id)
                    await connection.send_json({
                        "type": "ack",
                        "status": "processing"
                    })
                    
                    # 执行 Agent
                    try:
                        async with get_mysql_checkpointer() as checkpointer:
                            graph = build_graph(checkpointer=checkpointer)
                            
                            async for token in astream_agent(
                                graph=graph,
                                tenant_id=tenant_id,
                                user_id=user_id,
                                conversation_id=conversation_id,
                                message=content,
                            ):
                                # 检查是否被中断
                                if await interrupt_ctrl.check_interrupted(conversation_id):
                                    await connection.send_json({
                                        "type": "stopped",
                                        "conversation_id": conversation_id
                                    })
                                    await session_mgr.set_paused(conversation_id)
                                    break
                                
                                await connection.send_json({
                                    "type": "reply",
                                    "content": token
                                })
                        
                        # 完成
                        await connection.send_json({
                            "type": "done",
                            "conversation_id": conversation_id
                        })
                        await session_mgr.set_completed(conversation_id)
                        
                    except Exception as e:
                        logger.exception(f"[WebSocket] Agent 执行异常: {e}")
                        await connection.send_json({
                            "type": "error",
                            "message": str(e)
                        })
                        await session_mgr.set_stopped(conversation_id)
                
                elif msg_type == "stop":
                    # 停止对话
                    logger.info(f"[WebSocket] 收到停止请求: {conversation_id}")
                    
                    # 发送停止信号
                    from app.control.interrupt_controller import InterruptSignal
                    await interrupt_ctrl.send_signal(InterruptSignal(
                        conversation_id=conversation_id,
                        action="stop"
                    ))
                    
                    await connection.send_json({
                        "type": "stopped",
                        "conversation_id": conversation_id
                    })
                
                elif msg_type == "ping":
                    # 心跳
                    await connection.send_json({
                        "type": "pong"
                    })
                
                else:
                    await connection.send_json({
                        "type": "error",
                        "message": f"未知消息类型: {msg_type}"
                    })
            
            except json.JSONDecodeError:
                await connection.send_json({
                    "type": "error",
                    "message": "JSON 格式错误"
                })
    
    except WebSocketDisconnect:
        logger.info(f"[WebSocket] 连接断开: {conversation_id}")
    except Exception as e:
        logger.exception(f"[WebSocket] 异常: {e}")
    finally:
        connection.stop()
        await session_mgr.set_stopped(conversation_id)
        logger.info(f"[WebSocket] 连接关闭: {conversation_id}")
