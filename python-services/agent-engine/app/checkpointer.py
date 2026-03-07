"""
app/checkpointer.py — MySQL checkpointer 初始化

支持两种模式：
1. MySQL 模式：使用 AIOMySQLSaver 持久化
2. 内存模式：无持久化（开发测试用）
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from langgraph.checkpoint.mysql.aio import AIOMySQLSaver

logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_mysql_checkpointer() -> AsyncIterator[Optional["AIOMySQLSaver"]]:
    """
    Context manager：获取并初始化 AIOMySQLSaver。

    如果 MySQL 连接失败，自动降级为内存模式（checkpointer=None）。
    """
    saver = None
    try:
        from langgraph.checkpoint.mysql.aio import AIOMySQLSaver
        from app.config import settings

        # 检查是否有 MySQL 密码配置
        if not settings.mysql_pass:
            logger.info("MySQL 密码未配置，使用内存模式")
            yield None
            return

        conn_string = settings.mysql_url
        logger.debug("初始化 MySQL checkpointer: %s", conn_string.split("@")[-1])

        saver = AIOMySQLSaver.from_conn_string(conn_string)
        async with saver as s:
            await s.setup()
            logger.info("MySQL checkpointer 初始化完成")
            yield s

    except ImportError as e:
        logger.warning(f"MySQL 依赖未安装: {e}，使用内存模式")
        yield None
    except Exception as e:
        logger.warning(f"MySQL checkpointer 初始化失败: {e}，使用内存模式")
        yield None


class SimpleCheckpointer:
    """简单的内存 Checkpointer，用于开发测试"""

    def __init__(self):
        self._store = {}

    async def setup(self):
        pass

    async def aget(self, config):
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        return self._store.get(thread_id)

    async def aput(self, config, checkpoint, metadata=None):
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        self._store[thread_id] = checkpoint


# 全局内存 checkpointer
_memory_checkpointer = None


def get_memory_checkpointer():
    """获取内存 checkpointer（单例）"""
    global _memory_checkpointer
    if _memory_checkpointer is None:
        _memory_checkpointer = SimpleCheckpointer()
    return _memory_checkpointer
