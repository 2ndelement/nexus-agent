"""
main.py — RAG Service FastAPI 应用入口
端口：8003
"""
from __future__ import annotations

import logging

import uvicorn

import os
import socket
from common.nacos import create_registry
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


# ═══════════════════════════════════════════════════════════════════ Nacos 服务注册 ═══════════════════════════════════════════════════════════════════

def get_local_ip():
    """获取本机 IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def start_nacos_registry():
    """启动 Nacos 服务注册"""
    nacos_enabled = os.getenv("NACOS_ENABLED", "false").lower() == "true"
    if not nacos_enabled:
        print("[Nacos] 未启用 Nacos 服务注册")
        return
    
    service_name = os.getenv("NACOS_SERVICE_NAME", "nexus-rag-service")
    port = int(os.getenv("PORT", "8000"))
    ip = os.getenv("SERVICE_IP", get_local_ip())
    
    registry = create_registry(service_name, ip, port)
    registry.start()
    print(f"[Nacos] 服务注册完成: {service_name} -> {ip}:{port}")

# 启动时注册
start_nacos_registry()

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.rag_service_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
