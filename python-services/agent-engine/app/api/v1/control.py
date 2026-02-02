"""
app/api/v1/control.py — Agent 控制 API

接口：
- POST /stop - 停止对话
- POST /resume - 继续对话
- POST /inject - 插入消息
- GET /status - 查询状态
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.control.interrupt_controller import (
    InterruptController,
    InterruptSignal,
    get_interrupt_controller,
)
from app.control.session_manager import (
    ConversationStatus,
    get_session_manager,
)
from app.schemas import ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status/{conversation_id}")
async def get_conversation_status(
    conversation_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
):
    """
    查询对话状态
    
    Returns:
        - status: idle | running | paused | stopped | completed
        - message_count: 消息数量
    """
    session_mgr = await get_session_manager()
    interrupt_ctrl = await get_interrupt_controller()
    
    status = await session_mgr.get_status(conversation_id)
    is_interrupted = await interrupt_ctrl.check_interrupted(conversation_id)
    
    if status == "not_found":
        raise HTTPException(status_code=404, detail="对话不存在")
    
    return {
        "conversation_id": conversation_id,
        "status": status,
        "is_interrupted": is_interrupted,
    }


@router.post("/stop/{conversation_id}")
async def stop_conversation(
    conversation_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
):
    """
    停止对话
    
    发送停止信号，Agent 会在下次节点执行前检测到并中断
    """
    session_mgr = await get_session_manager()
    interrupt_ctrl = await get_interrupt_controller()
    
    # 检查状态
    status = await session_mgr.get_status(conversation_id)
    if status not in ["running", "paused"]:
        raise HTTPException(
            status_code=400,
            detail=f"无法停止：当前状态为 {status}"
        )
    
    # 发送停止信号
    await interrupt_ctrl.send_signal(InterruptSignal(
        conversation_id=conversation_id,
        action="stop",
    ))
    
    # 更新状态
    await session_mgr.set_stopped(conversation_id)
    
    logger.info(f"[Control API] 停止对话: {conversation_id}")
    
    return {
        "conversation_id": conversation_id,
        "status": "stopped",
        "message": "停止信号已发送"
    }


@router.post("/resume/{conversation_id}")
async def resume_conversation(
    conversation_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
):
    """
    继续对话
    
    从暂停点恢复执行
    """
    session_mgr = await get_session_manager()
    interrupt_ctrl = await get_interrupt_controller()
    
    # 检查状态
    status = await session_mgr.get_status(conversation_id)
    if status != "paused":
        raise HTTPException(
            status_code=400,
            detail=f"无法恢复：当前状态为 {status}，需要先发送消息"
        )
    
    # 清除中断信号
    interrupt_ctrl.clear_signal(conversation_id)
    
    # 更新状态
    await session_mgr.set_running(conversation_id)
    
    logger.info(f"[Control API] 恢复对话: {conversation_id}")
    
    return {
        "conversation_id": conversation_id,
        "status": "running",
        "message": "对话已恢复，可以继续发送消息"
    }


@router.post("/inject/{conversation_id}")
async def inject_message(
    conversation_id: str,
    body: dict,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
):
    """
    插入消息并继续对话
    
    当 Agent 暂停时，可以注入新消息并让它继续执行
    """
    session_mgr = await get_session_manager()
    interrupt_ctrl = await get_interrupt_controller()
    
    message = body.get("message")
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")
    
    # 检查状态
    status = await session_mgr.get_status(conversation_id)
    if status not in ["paused", "stopped"]:
        raise HTTPException(
            status_code=400,
            detail=f"无法注入消息：当前状态为 {status}"
        )
    
    # 获取当前 checkpoint 并修改 messages
    # TODO: 实现 checkpoint 修改逻辑
    # 需要访问 checkpointer 并修改状态
    
    # 发送注入信号
    await interrupt_ctrl.send_signal(InterruptSignal(
        conversation_id=conversation_id,
        action="inject",
        data={"message": message},
    ))
    
    # 更新状态为运行中
    await session_mgr.set_running(conversation_id)
    
    logger.info(f"[Control API] 注入消息: {conversation_id} - {message[:50]}...")
    
    return {
        "conversation_id": conversation_id,
        "status": "running",
        "message": "消息已注入，对话继续执行",
        "injected_message": message,
    }


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
):
    """
    删除对话
    
    清除所有状态和中断信号
    """
    session_mgr = await get_session_manager()
    interrupt_ctrl = await get_interrupt_controller()
    
    # 发送停止信号
    await interrupt_ctrl.send_signal(InterruptSignal(
        conversation_id=conversation_id,
        action="stop",
    ))
    
    # 清除状态
    interrupt_ctrl.clear_signal(conversation_id)
    
    # TODO: 清除 Redis 中的状态
    
    logger.info(f"[Control API] 删除对话: {conversation_id}")
    
    return {
        "conversation_id": conversation_id,
        "message": "对话已删除"
    }
