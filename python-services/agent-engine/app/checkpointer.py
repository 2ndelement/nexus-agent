"""
app/checkpointer.py — MySQL checkpointer 初始化

使用 AIOMySQLSaver（langgraph.checkpoint.mysql.aio）实现跨请求会话状态持久化。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from langgraph.checkpoint.mysql.aio import AIOMySQLSaver

from app.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_mysql_checkpointer() -> AsyncIterator[AIOMySQLSaver]:
    """
    Context manager：获取并初始化 AIOMySQLSaver。

    用法：
        async with get_mysql_checkpointer() as checkpointer:
            graph = build_graph(checkpointer)
            ...

    - 自动调用 setup() 确保 checkpoint 表存在（幂等）。
    - 连接串从 settings.mysql_url 读取（格式：mysql+aiomysql://...）。
    """
    conn_string = settings.mysql_url
    logger.debug("初始化 MySQL checkpointer: %s", conn_string.split("@")[-1])

    async with AIOMySQLSaver.from_conn_string(conn_string) as saver:
        await saver.setup()
        logger.info("MySQL checkpointer 初始化完成")
        yield saver
