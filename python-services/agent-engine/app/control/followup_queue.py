"""
app/control/followup_queue.py — Followup 消息队列

功能：
- 管理会话的 followup 消息队列
- 按顺序注入到 Agent
- 存储在 Redis 中（会话内短期）
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, asdict
from typing import Optional
import time

logger = logging.getLogger(__name__)


@dataclass
class FollowupMessage:
    """Followup 消息"""
    followup_id: str
    conversation_id: str
    content: str
    created_at: float
    injected: bool = False
    injected_at: Optional[float] = None


class FollowupQueue:
    """
    Followup 消息队列
    
    使用 Redis List 存储：
    - key: followup:{conversation_id}
    - value: JSON 序列化的 FollowupMessage 列表
    """

    def __init__(self):
        self._redis = None

    async def initialize(self):
        """初始化 Redis 连接"""
        try:
            import redis.asyncio as redis
            self._redis = redis.Redis(
                host=os.getenv("REDIS_HOST", "127.0.0.1"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                decode_responses=True,
            )
            logger.info("[FollowupQueue] Redis 连接成功")
        except Exception as e:
            logger.warning(f"[FollowupQueue] Redis 连接失败: {e}")
            self._redis = None

    def _key(self, conversation_id: str) -> str:
        """Redis key"""
        return f"followup:{conversation_id}"

    async def add(self, message: FollowupMessage) -> bool:
        """添加 followup 消息到队列"""
        if not self._redis:
            logger.warning("[FollowupQueue] Redis 未连接，无法添加")
            return False

        try:
            key = self._key(message.conversation_id)
            data = json.dumps(asdict(message))
            await self._redis.rpush(key, data)
            # 设置过期时间 24 小时
            await self._redis.expire(key, 24 * 3600)
            logger.info(f"[FollowupQueue] 添加消息: conv={message.conversation_id}, id={message.followup_id}")
            return True
        except Exception as e:
            logger.error(f"[FollowupQueue] 添加失败: {e}")
            return False

    async def get_pending(self, conversation_id: str) -> list[FollowupMessage]:
        """获取所有未注入的 followup 消息"""
        if not self._redis:
            return []

        try:
            key = self._key(conversation_id)
            items = await self._redis.lrange(key, 0, -1)
            
            result = []
            for item in items:
                msg = FollowupMessage(**json.loads(item))
                if not msg.injected:
                    result.append(msg)
            return result
        except Exception as e:
            logger.error(f"[FollowupQueue] 获取失败: {e}")
            return []

    async def mark_injected(self, conversation_id: str, followup_id: str) -> bool:
        """标记消息已注入"""
        if not self._redis:
            return False

        try:
            key = self._key(conversation_id)
            items = await self._redis.lrange(key, 0, -1)
            
            updated = []
            for item in items:
                msg = FollowupMessage(**json.loads(item))
                if msg.followup_id == followup_id:
                    msg.injected = True
                    msg.injected_at = time.time()
                updated.append(json.dumps(asdict(msg)))
            
            if updated:
                await self._redis.delete(key)
                await self._redis.rpush(key, *updated)
            
            return True
        except Exception as e:
            logger.error(f"[FollowupQueue] 标记失败: {e}")
            return False

    async def mark_all_injected(self, conversation_id: str) -> bool:
        """标记所有消息已注入"""
        if not self._redis:
            return False

        try:
            key = self._key(conversation_id)
            items = await self._redis.lrange(key, 0, -1)
            
            if not items:
                return True
            
            updated = []
            for item in items:
                msg = FollowupMessage(**json.loads(item))
                if not msg.injected:
                    msg.injected = True
                    msg.injected_at = time.time()
                updated.append(json.dumps(asdict(msg)))
            
            await self._redis.delete(key)
            if updated:
                await self._redis.rpush(key, *updated)
            
            return True
        except Exception as e:
            logger.error(f"[FollowupQueue] 批量标记失败: {e}")
            return False

    async def clear(self, conversation_id: str) -> bool:
        """清空队列"""
        if not self._redis:
            return False

        try:
            key = self._key(conversation_id)
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"[FollowupQueue] 清空失败: {e}")
            return False

    def has_pending(self, conversation_id: str) -> bool:
        """检查是否有未注入消息（同步版本，用于节点）"""
        # 实际使用时用异步版本
        return False


# 全局单例
_followup_queue: Optional[FollowupQueue] = None


async def get_followup_queue() -> FollowupQueue:
    """获取 Followup 队列"""
    global _followup_queue
    if _followup_queue is None:
        _followup_queue = FollowupQueue()
        await _followup_queue.initialize()
    return _followup_queue
