"""
app/schemas.py — Pydantic v2 请求/响应模型
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ─────────────────────────── Knowledge 文档管理 ───────────────────────────

class IngestRequest(BaseModel):
    """POST /api/v1/knowledge/ingest 请求体"""
    doc_id: str = Field(..., min_length=1, description="文档唯一 ID")
    content: str = Field(..., min_length=1, description="文档文本内容")
    knowledge_base_id: str = Field(..., min_length=1, description="知识库 ID")
    metadata: dict[str, Any] = Field(default_factory=dict, description="附加元数据")


class IngestResponse(BaseModel):
    """文档入库响应"""
    doc_id: str
    chunks_count: int
    knowledge_base_id: str
    message: str = "ingested"


class DeleteDocRequest(BaseModel):
    """POST /api/v1/knowledge/delete 请求体"""
    doc_id: str = Field(..., min_length=1)
    knowledge_base_id: str = Field(..., min_length=1)


class DeleteDocResponse(BaseModel):
    doc_id: str
    message: str = "deleted"


# ─────────────────────────── Retrieve 检索 ───────────────────────────

class RetrieveRequest(BaseModel):
    """POST /api/v1/knowledge/retrieve 请求体"""
    query: str = Field(..., min_length=1, description="检索查询词")
    knowledge_base_id: str = Field(..., min_length=1, description="知识库 ID")
    top_k: int = Field(default=5, ge=1, le=50, description="返回结果数量")


class RetrieveResult(BaseModel):
    """单条检索结果"""
    chunk_id: str
    doc_id: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrieveResponse(BaseModel):
    """检索响应"""
    query: str
    results: list[RetrieveResult]
    total: int


# ─────────────────────────── 通用 ───────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "rag-service"
