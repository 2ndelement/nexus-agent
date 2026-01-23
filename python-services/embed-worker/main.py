"""
main.py — embed-worker 入口

服务端口：无 HTTP 端口，纯 RabbitMQ 消费者
端口: N/A（仅消费消息）

依赖：
  - RabbitMQ: amqp://guest:guest@localhost:5672/
  - ChromaDB: localhost:8100
  - 模型: paraphrase-multilingual-MiniLM-L12-v2 (384维)
"""
from __future__ import annotations
import asyncio
import logging

import uvicorn

import os
import socket
from common.nacos import create_registry


async def async_main():
    from app.consumer import main as consumer_main
    await consumer_main()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info("启动 embed-worker (RabbitMQ 消费者)...")
    
    # 使用 asyncio.run 启动异步消费者
    asyncio.run(async_main())
