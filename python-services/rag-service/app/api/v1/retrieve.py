"""
app/api/v1/retrieve.py — 混合检索接口

POST /api/v1/knowledge/retrieve — Milvus 原生混合检索

Author: 帕托莉 🐱
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header

from app.dependencies import get_hybrid_retriever
from app.schemas import RetrieveRequest, RetrieveResponse, RetrieveResult

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve(
    body: RetrieveRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
):
    """
    Milvus 原生混合检索（稠密 + 稀疏 + RRF + Re-Rank）

    所有检索结果严格限定在 {tenant_id}:{knowledge_base_id} 范围内，
    不同租户数据完全隔离。

    检索流程：
    1. 生成查询向量（稠密 + 稀疏）
    2. Milvus 混合搜索
    3. RRF 融合排序
    4. Cross-Encoder Re-Rank（可选）
    """
    chunks = get_hybrid_retriever().retrieve(
        tenant_id=x_tenant_id,
        kb_id=body.knowledge_base_id,
        query=body.query,
        top_k=body.top_k,
    )

    results = [
        RetrieveResult(
            chunk_id=c.chunk_id,
            doc_id=c.doc_id,
            content=c.content,
            score=c.score,
            metadata=c.metadata,
        )
        for c in chunks
    ]

    logger.info(
        "retrieve: tenant=%s, kb=%s, query='%s', top_k=%d, found=%d",
        x_tenant_id, body.knowledge_base_id, body.query[:30], body.top_k, len(results),
    )

    return RetrieveResponse(
        query=body.query,
        results=results,
        total=len(results),
    )
