"""
app/schemas.py — Embed Service 数据模型
"""
from __future__ import annotations
from pydantic import BaseModel


class EmbedQueryRequest(BaseModel):
    """查询向量化请求"""
    text: str


class EmbedQueryResponse(BaseModel):
    """查询向量化响应"""
    embedding: list[float]
    dim: int
    cached: bool = False


class EmbedDocumentsRequest(BaseModel):
    """批量文档向量化请求"""
    texts: list[str]


class EmbedDocumentsResponse(BaseModel):
    """批量文档向量化响应"""
    embeddings: list[list[float]]
    dim: int
    count: int


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "ok"
    service: str = "embed-service"
    model: str = ""
    dim: int = 0
