"""
main.py — Embed Service FastAPI 应用入口

独立的向量化服务，提供：
- POST /api/v1/embed/query   — 单条查询向量化
- POST /api/v1/embed/documents — 批量文档向量化
- GET  /health — 健康检查

端口：8004
"""
from __future__ import annotations

import logging
import threading

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.embedder import get_embedder
from app.schemas import (
    EmbedQueryRequest,
    EmbedQueryResponse,
    EmbedDocumentsRequest,
    EmbedDocumentsResponse,
    HealthResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="NexusAgent — Embed Service",
    version="0.1.0",
    description="独立的向量化服务，支持 BGE 模型和 LRU 缓存",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def warmup():
    """启动时预热模型（后台线程）"""
    def _warmup():
        logger.info("[Warmup] 预热 Embedding 模型...")
        try:
            embedder = get_embedder()
            embedder.embed_query("warmup")
            logger.info(f"[Warmup] 模型预热完成，维度: {embedder.dim}")
        except Exception as e:
            logger.error(f"[Warmup] 预热失败: {e}")

    threading.Thread(target=_warmup, daemon=True).start()
    logger.info("[Warmup] 后台预热已启动")


@app.get("/health", response_model=HealthResponse)
def health():
    """健康检查"""
    embedder = get_embedder()
    return HealthResponse(
        model=settings.embedding_model,
        dim=embedder.dim if embedder._model else 0,
    )


@app.post("/api/v1/embed/query", response_model=EmbedQueryResponse)
def embed_query(body: EmbedQueryRequest):
    """
    单条查询向量化

    用于检索时将查询文本转为向量。
    支持 LRU 缓存，相同查询直接返回缓存结果。
    """
    embedder = get_embedder()
    embedding, cached = embedder.embed_query(body.text)

    return EmbedQueryResponse(
        embedding=embedding,
        dim=len(embedding),
        cached=cached,
    )


@app.post("/api/v1/embed/documents", response_model=EmbedDocumentsResponse)
def embed_documents(body: EmbedDocumentsRequest):
    """
    批量文档向量化

    用于文档入库时批量生成向量。
    """
    embedder = get_embedder()
    embeddings = embedder.embed_documents(body.texts)

    return EmbedDocumentsResponse(
        embeddings=embeddings,
        dim=len(embeddings[0]) if embeddings else 0,
        count=len(embeddings),
    )


@app.get("/api/v1/embed/cache/stats")
def cache_stats():
    """缓存统计"""
    embedder = get_embedder()
    return embedder.cache_stats()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
