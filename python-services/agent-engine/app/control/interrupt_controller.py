"""
app/control/interrupt_controller.py — 中断控制器（简化版）

只支持 stop 功能
"""
from __future__ import annotations

import logging
import os
from typing import Optional
from threading import Lock

logger = logging.getLogger(__name__)


class InterruptController:
    """
    中断控制器
    
    使用 Redis 存储中断信号
    """

    def __init__(self):
        self._redis = None
        self._local_flags: dict[str, bool] = {}
        self._lock = Lock()

    async def initialize(self):
        """初始化 Redis"""
        try:
            import redis.asyncio as redis
            self._redis = redis.Redis(
                host=os.getenv("REDIS_HOST", "127.0.0.1"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                decode_responses=True,
            )
            logger.info("[InterruptController] Redis 连接成功")
        except Exception as e:
            logger.warning(f"[InterruptController] Redis 连接失败: {e}")

    async def stop(self, conversation_id: str):
        """发送停止信号"""
        # 本地标记
        with self._lock:
            self._local_flags[conversation_id] = True
        
        # Redis 标记
        if self._redis:
            try:
                key = f"interrupt:stop:{conversation_id}"
                await self._redis.set(key, "1", ex=3600)
            except Exception as e:
                logger.error(f"[InterruptController] Redis 写入失败: {e}")

    def is_stopped(self, conversation_id: str) -> bool:
        """检查是否被停止"""
        # 本地检查
        with self._lock:
            if self._local_flags.get(conversation_id):
                return True
        
        return False

    def clear(self, conversation_id: str):
        """清除停止标记"""
        with self._lock:
            self._local_flags.pop(conversation_id, None)


# 全局单例
_interrupt_controller: Optional[InterruptController] = None


async def get_interrupt_controller() -> InterruptController:
    """获取中断控制器"""
    global _interrupt_controller
    if _interrupt_controller is None:
        _interrupt_controller = InterruptController()
        await _interrupt_controller.initialize()
    return _interrupt_controller
