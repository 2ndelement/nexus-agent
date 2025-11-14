"""
main.py — RAG Service FastAPI 应用入口
端口：8003
"""
from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.retrieve import router as retrieve_router
from app.schemas import HealthResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="NexusAgent — RAG Service",
    version="0.1.0",
    description="RAG 知识库检索服务：文档分片、向量化、BM25+向量混合检索（RRF）",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由（都挂在 /api/v1/knowledge 下）
app.include_router(knowledge_router, prefix="/api/v1/knowledge", tags=["knowledge"])
app.include_router(retrieve_router, prefix="/api/v1/knowledge", tags=["retrieve"])


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    return HealthResponse()


if __name__ == "__main__":
    from app.config import settings

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.rag_service_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
