"""
app/consumer.py — RabbitMQ 消费者

从 nexus.embed.tasks 队列消费消息，调用 embedder 向量化，写入 ChromaDB。
"""
from __future__ import annotations
import asyncio
import json
import logging

import aio_pika
from aio_pika import IncomingMessage
from aio_pika.abc import AbstractIncomingChannel

from app.config import settings
from app.schemas import EmbedTask, EmbedResult
from app.embedder import SentenceTransformerEmbedder, get_embedder
from app.chroma_writer import get_writer

logger = logging.getLogger(__name__)

# Embedder 实例（懒加载）
_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformerEmbedder(settings.embedding_model)
    return _embedder


async def process_embed_task(task: EmbedTask) -> EmbedResult:
    """
    处理单个向量化任务。
    流程：
      1. 提取所有 chunk 文本
      2. 批量调用 embedder
      3. 写入 ChromaDB
    """
    try:
        embedder = _get_embedder()
        writer = get_writer()

        # 提取文本
        texts = [c.content for c in task.chunks]
        
        # 批量向量化
        batch_size = settings.embedding_batch_size
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = embedder.embed_documents(batch)
            all_embeddings.extend(embeddings)

        # 写入 ChromaDB
        writer.write_chunks(
            tenant_id=task.tenant_id,
            kb_id=task.kb_id,
            chunks=task.chunks,
            embeddings=all_embeddings,
        )

        logger.info("向量化完成: task_id=%s, doc_id=%s, chunks=%d", 
                    task.task_id, task.doc_id, len(task.chunks))

        return EmbedResult(
            task_id=task.task_id,
            tenant_id=task.tenant_id,
            kb_id=task.kb_id,
            doc_id=task.doc_id,
            status="success",
            embedded_count=len(task.chunks),
        )

    except Exception as e:
        logger.exception("向量化失败: task_id=%s, error=%s", task.task_id, str(e))
        return EmbedResult(
            task_id=task.task_id,
            tenant_id=task.tenant_id,
            kb_id=task.kb_id,
            doc_id=task.doc_id,
            status="failed",
            error=str(e),
        )


async def on_message(message: IncomingMessage):
    """RabbitMQ 消息回调"""
    async with message.process():
        try:
            body = json.loads(message.body.decode())
            task = EmbedTask(**body)
            logger.debug("收到任务: task_id=%s, doc_id=%s", task.task_id, task.doc_id)

            result = await process_embed_task(task)

            # 可选：发布结果到 result exchange（供其他服务监听）
            # 这里简单打印，实际生产可发布到 nexus.embed.results
            if result.status == "success":
                logger.info("任务成功: task_id=%s", result.task_id)
            else:
                logger.error("任务失败: task_id=%s, error=%s", result.task_id, result.error)

        except Exception as e:
            logger.exception("消息处理异常: %s", str(e))


async def start_consumer():
    """启动消费者"""
    logger.info("连接 RabbitMQ: %s", settings.rabbitmq_url.replace("@", "@***"))
    
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel: AbstractIncomingChannel = await connection.channel()
    
    # 声明队列
    queue = await channel.declare_queue(
        settings.embed_queue,
        durable=True,  # 持久化，重启不丢
    )

    # 设置预取数（并发控制）
    await channel.set_qos(prefetch_count=settings.worker_concurrency)

    logger.info("开始消费队列: %s, 并发: %d", 
                settings.embed_queue, settings.worker_concurrency)

    await queue.consume(on_message)

    # 保持运行
    await asyncio.Future()  # 永远等待


async def main():
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("启动 embed-worker...")
    await start_consumer()
