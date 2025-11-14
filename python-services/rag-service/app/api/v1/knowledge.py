"""
app/api/v1/knowledge.py — 文档管理接口

POST /api/v1/knowledge/ingest   — 文档写入（分片 + 向量化 + 入库）
POST /api/v1/knowledge/delete   — 文档删除
GET  /api/v1/knowledge/count    — chunk 数量查询
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header

from app.chunker import chunk_document
from app.dependencies import get_hybrid_retriever, get_retriever
from app.embedder import get_embedder
from app.retriever.chroma_retriever import ChromaRetriever
from app.schemas import (
    DeleteDocRequest,
    DeleteDocResponse,
    IngestRequest,
    IngestResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest_document(
    body: IngestRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    retriever: ChromaRetriever = Depends(get_retriever),
):
    """
    文档写入。

    流程：
    1. 文档分片（chunker）
    2. 批量向量化（embedder）
    3. 写入 ChromaDB（collection = nexus_{tenant_id}_{kb_id}）
    """
    chunks = chunk_document(
        doc_id=body.doc_id,
        content=body.content,
        metadata=body.metadata,
    )

    embedder = get_embedder()
    texts = [c.content for c in chunks]
    embeddings = embedder.embed_documents(texts)

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


@router.post("/delete", response_model=DeleteDocResponse)
def delete_document(
    body: DeleteDocRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    retriever: ChromaRetriever = Depends(get_retriever),
):
    """删除指定文档的所有 chunks。"""
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
    retriever: ChromaRetriever = Depends(get_retriever),
):
    """查询指定知识库的 chunk 总数。"""
    n = retriever.count(tenant_id=x_tenant_id, kb_id=knowledge_base_id)
    return {"tenant_id": x_tenant_id, "knowledge_base_id": knowledge_base_id, "count": n}
