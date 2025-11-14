"""
app/api/v1/retrieve.py — 混合检索接口

POST /api/v1/knowledge/retrieve — BM25 + 向量 RRF 混合检索
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header

from app.dependencies import get_hybrid_retriever
from app.retriever.hybrid import HybridRetriever
from app.schemas import RetrieveRequest, RetrieveResponse, RetrieveResult

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve(
    body: RetrieveRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    hybrid: HybridRetriever = Depends(get_hybrid_retriever),
):
    """
    混合检索（BM25 + 向量 RRF）。

    所有检索结果严格限定在 {tenant_id}:{knowledge_base_id} 范围内，
    不同租户数据完全隔离（collection 命名隔离）。
    """
    chunks = hybrid.retrieve(
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
