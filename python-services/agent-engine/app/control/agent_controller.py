"""
app/control/agent_controller.py — Agent 中断控制器

功能：
1. 停止对话（设置中断标志）
2. 继续对话（恢复执行）
3. 注入消息（修改状态后继续）
4. 查询状态
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.control.conversation_manager import (
    ConversationManager,
    ConversationStatus,
    get_conversation_manager,
)

logger = logging.getLogger(__name__)


@dataclass
class InterruptReason:
    """中断原因"""
    reason: str  # "user_stop", "timeout", "error", etc.
    message: str  # 详细描述
    timestamp: datetime


class AgentController:
    """
    Agent 中断控制器
    
    管理对话的中断和恢复：
    - 停止：设置 interrupt flag，Agent 在检查点暂停
    - 恢复：从检查点继续执行
    - 注入：在检查点修改状态后继续
    """
    
    def __init__(self, conversation_manager: Optional[ConversationManager] = None):
        self._conv_manager = conversation_manager or get_conversation_manager()
        # conversation_id -> InterruptReason
        self._interrupt_reasons: dict[str, InterruptReason] = {}
        # conversation_id -> 新消息（用于注入）
        self._pending_messages: dict[str, str] = {}
    
    def stop(self, conversation_id: str, reason: str = "user_stop") -> bool:
        """
        停止对话
        
        Args:
            conversation_id: 对话ID
            reason: 停止原因
        
        Returns:
            是否成功
        """
        # 更新状态为 PAUSED
        success = self._conv_manager.update_status(conversation_id, ConversationStatus.PAUSED)
        
        if success:
            # 记录中断原因
            self._interrupt_reasons[conversation_id] = InterruptReason(
                reason=reason,
                message=f"用户停止对话: {reason}",
                timestamp=datetime.now(),
            )
            logger.info(f"[AgentController] 对话停止: {conversation_id}, reason={reason}")
        else:
            logger.warning(f"[AgentController] 停止失败，对话不存在: {conversation_id}")
        
        return success
    
    def resume(self, conversation_id: str) -> bool:
        """
        继续对话
        
        Args:
            conversation_id: 对话ID
        
        Returns:
            是否成功
        """
        # 检查是否为 PAUSED 状态
        meta = self._conv_manager.get(conversation_id)
        if not meta:
            logger.warning(f"[AgentController] 恢复失败，对话不存在: {conversation_id}")
            return False
        
        if meta.status != ConversationStatus.PAUSED:
            logger.warning(f"[AgentController] 恢复失败，状态不正确: {conversation_id}, status={meta.status}")
            return False
        
        # 更新状态为 RUNNING
        success = self._conv_manager.update_status(conversation_id, ConversationStatus.RUNNING)
        
        if success:
            # 清除中断原因
            self._interrupt_reasons.pop(conversation_id, None)
            logger.info(f"[AgentController] 对话恢复: {conversation_id}")
        
        return success
    
    def inject_message(self, conversation_id: str, message: str) -> bool:
        """
        注入消息到对话
        
        Args:
            conversation_id: 对话ID
            message: 新消息内容
        
        Returns:
            是否成功
        """
        # 检查是否为 PAUSED 状态
        meta = self._conv_manager.get(conversation_id)
        if not meta:
            logger.warning(f"[AgentController] 注入失败，对话不存在: {conversation_id}")
            return False
        
        if meta.status != ConversationStatus.PAUSED:
            logger.warning(f"[AgentController] 注入失败，状态不正确: {conversation_id}, status={meta.status}")
            return False
        
        # 保存待注入的消息
        self._pending_messages[conversation_id] = message
        
        # 更新状态为 RUNNING
        success = self._conv_manager.update_status(conversation_id, ConversationStatus.RUNNING)
        
        if success:
            # 清除中断原因
            self._interrupt_reasons.pop(conversation_id, None)
            logger.info(f"[AgentController] 消息注入: {conversation_id}, message={message[:50]}...")
        
        return success
    
    def is_interrupted(self, conversation_id: str) -> bool:
        """
        检查对话是否被中断
        
        Args:
            conversation_id: 对话ID
        
        Returns:
            是否被中断
        """
        return conversation_id in self._interrupt_reasons
    
    def get_interrupt_reason(self, conversation_id: str) -> Optional[InterruptReason]:
        """
        获取中断原因
        
        Args:
            conversation_id: 对话ID
        
        Returns:
            中断原因，如果没有中断则返回 None
        """
        return self._interrupt_reasons.get(conversation_id)
    
    def get_pending_message(self, conversation_id: str) -> Optional[str]:
        """
        获取待注入的消息
        
        Args:
            conversation_id: 对话ID
        
        Returns:
            待注入的消息，如果没有则返回 None
        """
        return self._pending_messages.pop(conversation_id, None)
    
    def has_pending_message(self, conversation_id: str) -> bool:
        """
        检查是否有待注入的消息
        
        Args:
            conversation_id: 对话ID
        
        Returns:
            是否有待注入消息
        """
        return conversation_id in self._pending_messages
    
    def get_status(self, conversation_id: str) -> Optional[ConversationStatus]:
        """
        获取对话状态
        
        Args:
            conversation_id: 对话ID
        
        Returns:
            对话状态
        """
        meta = self._conv_manager.get(conversation_id)
        return meta.status if meta else None
    
    def complete(self, conversation_id: str) -> bool:
        """
        标记对话为完成
        
        Args:
            conversation_id: 对话ID
        
        Returns:
            是否成功
        """
        # 清除所有相关状态
        self._interrupt_reasons.pop(conversation_id, None)
        self._pending_messages.pop(conversation_id, None)
        
        return self._conv_manager.update_status(conversation_id, ConversationStatus.COMPLETED)


# 全局单例
_agent_controller: Optional[AgentController] = None


def get_agent_controller() -> AgentController:
    """获取全局 Agent 控制器"""
    global _agent_controller
    if _agent_controller is None:
        _agent_controller = AgentController()
    return _agent_controller
