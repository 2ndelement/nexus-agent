"""
app/consumer.py — RabbitMQ 消费者

从 nexus.embed.tasks 队列消费消息，进行 embedding 并写入向量库。
"""
from __future__ import annotations
import asyncio
import json
import logging

import aio_pika
from aio_pika import IncomingMessage
from aio_pika.abc import AbstractChannel

from app.config import settings
from app.schemas import EmbedTask, EmbedResult

logger = logging.getLogger(__name__)


async def process_embed_task(task: EmbedTask) -> EmbedResult:
    """
    处理向量化任务

    流程：
      1. 调用 Embed Service 进行 embedding
      2. 写入 Milvus/ChromaDB
    """
    try:
        import httpx
        import os

        texts = [c.content for c in task.chunks]

        # 调用 Embed Service 进行 embedding
        if settings.use_embed_service:
            logger.info("调用 Embed Service: %s", settings.embed_service_url)
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{settings.embed_service_url}/api/v1/embed/documents",
                    json={"texts": texts},
                )
                response.raise_for_status()
                embeddings = response.json()["embeddings"]
        else:
            # 本地 embedding（备用）
            from app.bge_embedder import get_embedder
            embedder = get_embedder()
            embeddings = embedder.embed_documents(texts)

        # 写入向量库
        from app.rag_dependencies import get_milvus_retriever
        retriever = get_milvus_retriever()
        retriever.add_chunks(
            tenant_id=task.tenant_id,
            kb_id=task.kb_id,
            chunk_ids=[c.chunk_id for c in task.chunks],
            doc_ids=[task.doc_id] * len(task.chunks),
            contents=texts,
            embeddings=embeddings,
            metadatas=[c.metadata for c in task.chunks],
        )

        logger.info(
            "向量化完成: task_id=%s, doc_id=%s, chunks=%d",
            task.task_id, task.doc_id, len(task.chunks)
        )

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
            logger.info("收到任务: task_id=%s, doc_id=%s, chunks=%d",
                       task.task_id, task.doc_id, len(task.chunks))

            result = await process_embed_task(task)

            if result.status == "success":
                logger.info("任务成功: task_id=%s, embedded=%d",
                           result.task_id, result.embedded_count)
            else:
                logger.error("任务失败: task_id=%s, error=%s",
                            result.task_id, result.error)

        except Exception as e:
            logger.exception("消息处理异常: %s", str(e))


async def warmup_models():
    """预热：检查 Embed Service 连接"""
    import httpx
    if settings.use_embed_service:
        logger.info("[Warmup] 检查 Embed Service 连接...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{settings.embed_service_url}/health")
                response.raise_for_status()
                logger.info("[Warmup] Embed Service 连接正常")
        except Exception as e:
            logger.warning(f"[Warmup] Embed Service 连接失败: {e}")
    else:
        logger.info("[Warmup] 预热本地 Embedding 模型...")
        try:
            from app.bge_embedder import get_embedder
            embedder = get_embedder()
            embedder.embed_query("warmup")
            logger.info("[Warmup] Embedding 模型预热完成")
        except Exception as e:
            logger.warning(f"[Warmup] Embedding 模型预热失败: {e}")


async def start_consumer():
    """启动消费者"""
    # 先预热模型
    await warmup_models()

    logger.info("连接 RabbitMQ: %s", settings.rabbitmq_url.replace("guest:guest", "***:***"))

    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel: AbstractChannel = await connection.channel()

    # 声明队列
    queue = await channel.declare_queue(
        settings.embed_queue,
        durable=True,
    )

    # 设置预取数
    await channel.set_qos(prefetch_count=settings.worker_concurrency)

    logger.info("开始消费队列: %s, 并发: %d",
                settings.embed_queue, settings.worker_concurrency)

    await queue.consume(on_message)

    # 保持运行
    await asyncio.Future()


async def main():
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("启动 embed-worker (使用 RAG service 模块)...")
    await start_consumer()


if __name__ == "__main__":
    asyncio.run(main())
