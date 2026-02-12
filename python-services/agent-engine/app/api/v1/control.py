"""
app/api/v1/control.py — Agent 控制 API（简化版）

接口：
- POST /stop - 停止对话
- GET /status - 查询状态
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.control.interrupt_controller import get_interrupt_controller

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status/{conversation_id}")
async def get_conversation_status(
    conversation_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
):
    """
    查询对话状态
    """
    interrupt_ctrl = await get_interrupt_controller()
    is_stopped = interrupt_ctrl.is_stopped(conversation_id)
    
    return {
        "conversation_id": conversation_id,
        "status": "stopped" if is_stopped else "running",
        "is_stopped": is_stopped,
    }


@router.post("/stop/{conversation_id}")
async def stop_conversation(
    conversation_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
):
    """
    停止对话
    
    发送停止信号，Agent 会在下次检查时中断
    """
    interrupt_ctrl = await get_interrupt_controller()
    await interrupt_ctrl.stop(conversation_id)
    
    logger.info(f"[Control API] 停止对话: {conversation_id}")
    
    return {
        "conversation_id": conversation_id,
        "status": "stopped",
        "message": "停止信号已发送"
    }


@router.delete("/{conversation_id}")
async def clear_stop(
    conversation_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
):
    """
    清除停止标记（用于恢复）
    """
    interrupt_ctrl = await get_interrupt_controller()
    interrupt_ctrl.clear(conversation_id)
    
    return {
        "conversation_id": conversation_id,
        "message": "停止标记已清除"
    }
