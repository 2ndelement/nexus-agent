"""
main.py — FastAPI 应用入口

服务端口：8001
"""
from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.chat import router as chat_router
from app.schemas import HealthResponse

# ─────────────────────────── 日志 ───────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────── 应用 ───────────────────────────
app = FastAPI(
    title="NexusAgent — Agent Engine",
    version="0.1.0",
    description="Python 核心 AI 服务：LangGraph Agent + MySQL Checkpoint + SSE 流式输出",
)

# CORS（开发环境宽松，生产由 Gateway 控制）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────── 路由 ───────────────────────────
app.include_router(chat_router, prefix="/api/v1/agent")


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """健康检查接口，供 K8s/Docker 探针使用。"""
    return HealthResponse()


# ─────────────────────────── 启动 ───────────────────────────
if __name__ == "__main__":
    from app.config import settings

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.agent_engine_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
