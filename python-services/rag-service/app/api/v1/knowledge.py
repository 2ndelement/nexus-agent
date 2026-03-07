"""
app/api/v1/knowledge.py — 文档管理接口

POST /api/v1/knowledge/ingest       — 文档写入（同步，分块 + 向量化 + 入库）
POST /api/v1/knowledge/ingest_async — 文档写入（异步，发送到消息队列）
POST /api/v1/knowledge/delete       — 文档删除
GET  /api/v1/knowledge/count        — chunk 数量查询

Author: 帕托莉 🐱
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

import aio_pika
from fastapi import APIRouter, Depends, Header, BackgroundTasks

from app.chunker import chunk_document
from app.dependencies import get_milvus_retriever
from app.embedder import get_embedder
from app.schemas import (
    DeleteDocRequest,
    DeleteDocResponse,
    IngestRequest,
    IngestResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# RabbitMQ 配置
RABBITMQ_URL = "amqp://guest:guest@localhost:5672/"
EMBED_QUEUE = "nexus.embed.tasks"


async def send_to_queue(task_data: dict):
    """发送任务到 RabbitMQ 队列"""
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()

            # 声明队列
            queue = await channel.declare_queue(EMBED_QUEUE, durable=True)

            # 发送消息
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(task_data).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=EMBED_QUEUE,
            )

            logger.info("任务已发送到队列: task_id=%s", task_data.get("task_id"))
    except Exception as e:
        logger.error("发送消息到队列失败: %s", e)
        raise


@router.post("/ingest", response_model=IngestResponse)
def ingest_document(
    body: IngestRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
):
    """
    文档写入。

    流程：
    1. 文档分块（chunker）
    2. 批量向量化（embedder）
    3. 写入 Milvus（collection = nexus_{tenant_id}_{kb_id}）
    """
    chunks = chunk_document(
        doc_id=body.doc_id,
        content=body.content,
        metadata=body.metadata,
    )

    embedder = get_embedder()
    texts = [c.content for c in chunks]
    embeddings = embedder.embed_documents(texts)

    retriever = get_milvus_retriever()
    retriever.add_chunks(
        tenant_id=x_tenant_id,
        kb_id=body.knowledge_base_id,
        chunk_ids=[c.chunk_id for c in chunks],
        doc_ids=[c.doc_id for c in chunks],
        contents=texts,
        embeddings=embeddings,
        metadatas=[c.metadata for c in chunks],
    )

    logger.info(
        "ingest: tenant=%s, kb=%s, doc=%s, chunks=%d",
        x_tenant_id, body.knowledge_base_id, body.doc_id, len(chunks),
    )

    return IngestResponse(
        doc_id=body.doc_id,
        chunks_count=len(chunks),
        knowledge_base_id=body.knowledge_base_id,
    )


class IngestAsyncResponse(IngestResponse):
    """异步入库响应"""
    task_id: str
    status: str = "queued"


@router.post("/ingest_async")
async def ingest_document_async(
    body: IngestRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
):
    """
    异步文档写入（发送到消息队列）。

    流程：
    1. 文档分块（chunker）
    2. 发送到 RabbitMQ 队列
    3. embed-worker 消费处理

    返回 task_id 供后续查询状态。
    """
    # 生成任务 ID
    task_id = f"task-{uuid.uuid4().hex[:12]}"

    # 分块
    chunks = chunk_document(
        doc_id=body.doc_id,
        content=body.content,
        metadata=body.metadata,
    )

    # 构造任务消息
    task_data = {
        "task_id": task_id,
        "tenant_id": x_tenant_id,
        "kb_id": body.knowledge_base_id,
        "doc_id": body.doc_id,
        "chunks": [
            {
                "chunk_id": c.chunk_id,
                "chunk_index": i,
                "content": c.content,
                "metadata": c.metadata,
            }
            for i, c in enumerate(chunks)
        ],
    }

    # 发送到队列
    await send_to_queue(task_data)

    logger.info(
        "ingest_async: tenant=%s, kb=%s, doc=%s, chunks=%d, task_id=%s",
        x_tenant_id, body.knowledge_base_id, body.doc_id, len(chunks), task_id,
    )

    return {
        "task_id": task_id,
        "doc_id": body.doc_id,
        "chunks_count": len(chunks),
        "knowledge_base_id": body.knowledge_base_id,
        "status": "queued",
        "message": "文档已提交到处理队列",
    }


@router.post("/delete", response_model=DeleteDocResponse)
def delete_document(
    body: DeleteDocRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
):
    """
    删除指定文档的所有 chunks。
    """
    retriever = get_milvus_retriever()
    retriever.delete_doc(
        tenant_id=x_tenant_id,
        kb_id=body.knowledge_base_id,
        doc_id=body.doc_id,
    )
    return DeleteDocResponse(doc_id=body.doc_id)


@router.get("/count")
def get_count(
    knowledge_base_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
):
    """
    查询指定知识库的 chunk 总数。
    """
    retriever = get_milvus_retriever()
    n = retriever.count(tenant_id=x_tenant_id, kb_id=knowledge_base_id)
    return {"tenant_id": x_tenant_id, "knowledge_base_id": knowledge_base_id, "count": n}
