"""
app/schemas.py — embed-worker 消息 Schema

消息流:
  nexus-knowledge (Java) 
      → RabbitMQ queue: nexus.embed.tasks
      → embed-worker 消费
      → 向量写入 ChromaDB
      → 发布结果到 exchange: nexus.embed.results (可选，供 knowledge-service 监听状态)

消息格式 (JSON):
{
    "task_id":     "uuid",
    "tenant_id":   "1",
    "kb_id":       "101",
    "doc_id":      "9001",
    "chunks": [
        {
            "chunk_id":    "abc123",
            "chunk_index": 0,
            "content":     "文本内容...",
            "metadata":    {"filename": "x.pdf", "page": 1}
        },
        ...
    ]
}
"""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class ChunkPayload(BaseModel):
    chunk_id: str
    chunk_index: int
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmbedTask(BaseModel):
    """RabbitMQ 消息体：一次文档向量化任务"""
    task_id: str
    tenant_id: str
    kb_id: str
    doc_id: str
    chunks: list[ChunkPayload]


class EmbedResult(BaseModel):
    """处理结果，发布到 result exchange"""
    task_id: str
    tenant_id: str
    kb_id: str
    doc_id: str
    status: str           # "success" | "failed"
    embedded_count: int = 0
    error: str | None = None
