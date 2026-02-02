"""
app/control/conversation_manager.py — 对话状态管理器

管理对话的生命周期：
- 对话状态：RUNNING / PAUSED / COMPLETED / STOPPED
- 对话元数据：创建时间、最后活跃时间、消息数等
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import threading

logger = logging.getLogger(__name__)


class ConversationStatus(str, Enum):
    """对话状态"""
    IDLE = "IDLE"           # 空闲（等待用户输入）
    RUNNING = "RUNNING"      # 正在执行
    PAUSED = "PAUSED"        # 已暂停（用户点击停止）
    COMPLETED = "COMPLETED"   # 已完成
    STOPPED = "STOPPED"      # 被用户停止


@dataclass
class ConversationMetadata:
    """对话元数据"""
    conversation_id: str
    tenant_id: str
    user_id: str
    status: ConversationStatus = ConversationStatus.IDLE
    created_at: datetime = field(default_factory=datetime.now)
    last_active_at: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    current_node: Optional[str] = None  # 当前执行的节点
    checkpoint_id: Optional[str] = None  # 当前检查点ID


class ConversationManager:
    """
    对话状态管理器
    
    线程安全，支持并发访问
    """
    
    def __init__(self):
        # conversation_id -> ConversationMetadata
        self._conversations: dict[str, ConversationMetadata] = {}
        self._lock = threading.RLock()
    
    def create(self, conversation_id: str, tenant_id: str, user_id: str) -> ConversationMetadata:
        """创建新对话"""
        with self._lock:
            meta = ConversationMetadata(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            self._conversations[conversation_id] = meta
            logger.info(f"[ConvManager] 创建对话: {conversation_id}")
            return meta
    
    def get(self, conversation_id: str) -> Optional[ConversationMetadata]:
        """获取对话元数据"""
        with self._lock:
            return self._conversations.get(conversation_id)
    
    def exists(self, conversation_id: str) -> bool:
        """检查对话是否存在"""
        with self._lock:
            return conversation_id in self._conversations
    
    def update_status(self, conversation_id: str, status: ConversationStatus) -> bool:
        """更新对话状态"""
        with self._lock:
            meta = self._conversations.get(conversation_id)
            if meta:
                meta.status = status
                meta.last_active_at = datetime.now()
                logger.info(f"[ConvManager] 状态更新: {conversation_id} -> {status}")
                return True
            return False
    
    def update_node(self, conversation_id: str, node: str) -> bool:
        """更新当前执行节点"""
        with self._lock:
            meta = self._conversations.get(conversation_id)
            if meta:
                meta.current_node = node
                meta.last_active_at = datetime.now()
                return True
            return False
    
    def update_checkpoint(self, conversation_id: str, checkpoint_id: str) -> bool:
        """更新当前检查点"""
        with self._lock:
            meta = self._conversations.get(conversation_id)
            if meta:
                meta.checkpoint_id = checkpoint_id
                return True
            return False
    
    def increment_message_count(self, conversation_id: str) -> int:
        """增加消息计数"""
        with self._lock:
            meta = self._conversations.get(conversation_id)
            if meta:
                meta.message_count += 1
                meta.last_active_at = datetime.now()
                return meta.message_count
            return 0
    
    def is_running(self, conversation_id: str) -> bool:
        """检查对话是否正在运行"""
        with self._lock:
            meta = self._conversations.get(conversation_id)
            return meta is not None and meta.status == ConversationStatus.RUNNING
    
    def is_paused(self, conversation_id: str) -> bool:
        """检查对话是否已暂停"""
        with self._lock:
            meta = self._conversations.get(conversation_id)
            return meta is not None and meta.status == ConversationStatus.PAUSED
    
    def remove(self, conversation_id: str) -> bool:
        """移除对话"""
        with self._lock:
            if conversation_id in self._conversations:
                del self._conversations[conversation_id]
                logger.info(f"[ConvManager] 移除对话: {conversation_id}")
                return True
            return False
    
    def list_active(self) -> list[ConversationMetadata]:
        """列出所有活跃对话"""
        with self._lock:
            return [
                meta for meta in self._conversations.values()
                if meta.status in (ConversationStatus.RUNNING, ConversationStatus.PAUSED)
            ]
    
    def cleanup_idle(self, max_idle_seconds: int = 3600) -> int:
        """清理空闲对话"""
        with self._lock:
            now = datetime.now()
            to_remove = []
            
            for conv_id, meta in self._conversations.items():
                idle_seconds = (now - meta.last_active_at).total_seconds()
                if idle_seconds > max_idle_seconds and meta.status == ConversationStatus.IDLE:
                    to_remove.append(conv_id)
            
            for conv_id in to_remove:
                del self._conversations[conv_id]
            
            if to_remove:
                logger.info(f"[ConvManager] 清理空闲对话: {len(to_remove)} 个")
            
            return len(to_remove)


# 全局单例
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """获取全局对话管理器"""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager
