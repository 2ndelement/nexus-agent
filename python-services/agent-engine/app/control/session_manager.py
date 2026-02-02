"""
app/control/session_manager.py — 会话状态管理器

状态机：
  IDLE → RUNNING → PAUSED → RUNNING → COMPLETED
                  ↓
               STOPPED

支持功能：
- 对话状态持久化
- 中断信号管理
- 断点恢复
"""
from __future__ import annotations

import asyncio
import enum
import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from threading import Lock

logger = logging.getLogger(__name__)


class ConversationStatus(enum.Enum):
    """对话状态"""
    IDLE = "idle"           # 空闲
    RUNNING = "running"     # 运行中
    PAUSED = "paused"      # 已暂停
    STOPPED = "stopped"    # 已停止
    COMPLETED = "completed"  # 已完成


@dataclass
class ConversationState:
    """对话状态"""
    conversation_id: str
    status: ConversationStatus = ConversationStatus.IDLE
    started_at: float = field(default_factory=time.time)
    paused_at: Optional[float] = None
    last_message: Optional[str] = None
    last_checkpoint_id: Optional[str] = None
    message_count: int = 0


class SessionManager:
    """
    会话状态管理器
    
    使用内存 + Redis 持久化
    - 内存：快速读写
    - Redis：跨进程共享、重启恢复
    """

    def __init__(self):
        self._states: dict[str, ConversationState] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._lock = Lock()
        self._redis_client = None

    async def initialize(self):
        """初始化 Redis 连接"""
        try:
            import redis.asyncio as redis
            self._redis_client = redis.Redis(
                host=os.getenv("REDIS_HOST", "127.0.0.1"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                decode_responses=True,
            )
            logger.info("[SessionManager] Redis 连接成功")
        except Exception as e:
            logger.warning(f"[SessionManager] Redis 连接失败，使用内存存储: {e}")
            self._redis_client = None

    def _get_lock(self, conversation_id: str) -> asyncio.Lock:
        """获取对话锁"""
        with self._lock:
            if conversation_id not in self._locks:
                self._locks[conversation_id] = asyncio.Lock()
            return self._locks[conversation_id]

    async def get_state(self, conversation_id: str) -> Optional[ConversationState]:
        """获取对话状态"""
        # 先查内存
        if conversation_id in self._states:
            return self._states[conversation_id]
        
        # 再查 Redis
        if self._redis_client:
            try:
                key = f"conv:state:{conversation_id}"
                data = await self._redis_client.hgetall(key)
                if data:
                    state = ConversationState(
                        conversation_id=conversation_id,
                        status=ConversationStatus(data.get("status", "idle")),
                        started_at=float(data.get("started_at", time.time())),
                        paused_at=float(data["paused_at"]) if data.get("paused_at") else None,
                        last_message=data.get("last_message"),
                        last_checkpoint_id=data.get("last_checkpoint_id"),
                        message_count=int(data.get("message_count", 0)),
                    )
                    self._states[conversation_id] = state
                    return state
            except Exception as e:
                logger.error(f"[SessionManager] Redis 读取失败: {e}")
        
        return None

    async def update_state(self, state: ConversationState):
        """更新对话状态"""
        # 更新内存
        self._states[state.conversation_id] = state
        
        # 持久化到 Redis
        if self._redis_client:
            try:
                key = f"conv:state:{state.conversation_id}"
                data = {
                    "status": state.status.value,
                    "started_at": str(state.started_at),
                    "paused_at": str(state.paused_at) if state.paused_at else "",
                    "last_message": state.last_message or "",
                    "last_checkpoint_id": state.last_checkpoint_id or "",
                    "message_count": str(state.message_count),
                }
                await self._redis_client.hset(key, mapping=data)
                # 设置过期时间 7 天
                await self._redis_client.expire(key, 7 * 24 * 3600)
            except Exception as e:
                logger.error(f"[SessionManager] Redis 写入失败: {e}")

    async def create_conversation(self, conversation_id: str) -> ConversationState:
        """创建新对话"""
        state = ConversationState(conversation_id=conversation_id)
        await self.update_state(state)
        return state

    async def set_running(self, conversation_id: str):
        """设置运行中"""
        state = await self.get_state(conversation_id)
        if not state:
            state = await self.create_conversation(conversation_id)
        
        state.status = ConversationStatus.RUNNING
        state.paused_at = None
        await self.update_state(state)
        logger.info(f"[SessionManager] 对话 {conversation_id} 设置为 RUNNING")

    async def set_paused(self, conversation_id: str, checkpoint_id: Optional[str] = None):
        """设置暂停"""
        state = await self.get_state(conversation_id)
        if state:
            state.status = ConversationStatus.PAUSED
            state.paused_at = time.time()
            if checkpoint_id:
                state.last_checkpoint_id = checkpoint_id
            await self.update_state(state)
            logger.info(f"[SessionManager] 对话 {conversation_id} 设置为 PAUSED")

    async def set_stopped(self, conversation_id: str):
        """设置停止"""
        state = await self.get_state(conversation_id)
        if state:
            state.status = ConversationStatus.STOPPED
            await self.update_state(state)
            logger.info(f"[SessionManager] 对话 {conversation_id} 设置为 STOPPED")

    async def set_completed(self, conversation_id: str):
        """设置完成"""
        state = await self.get_state(conversation_id)
        if state:
            state.status = ConversationStatus.COMPLETED
            await self.update_state(state)
            logger.info(f"[SessionManager] 对话 {conversation_id} 设置为 COMPLETED")

    async def increment_message_count(self, conversation_id: str):
        """增加消息计数"""
        state = await self.get_state(conversation_id)
        if state:
            state.message_count += 1
            await self.update_state(state)

    def is_running(self, conversation_id: str) -> bool:
        """检查是否运行中"""
        state = self._states.get(conversation_id)
        return state is not None and state.status == ConversationStatus.RUNNING

    async def get_status(self, conversation_id: str) -> str:
        """获取状态字符串"""
        state = await self.get_state(conversation_id)
        if not state:
            return "not_found"
        return state.status.value


# 全局单例
_session_manager: Optional[SessionManager] = None


async def get_session_manager() -> SessionManager:
    """获取会话管理器单例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
        await _session_manager.initialize()
    return _session_manager
