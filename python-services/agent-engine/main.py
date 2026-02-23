"""
main.py — FastAPI 应用入口

服务端口：8001
支持 Nacos 服务注册
"""
from __future__ import annotations

import logging
import os
import socket
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.chat import router as chat_router
from app.api.v1.control import router as control_router
from app.api.v1.websocket import router as websocket_router
from app.api.v1.admin import router as admin_router
from app.api.v1.models import router as models_router
from app.api.v1.media import router as media_router
from app.schemas import HealthResponse
from common.nacos import create_registry, NacosServiceRegistry

# ═══════════════════════════════════════════════════════════════════ 日志 ═══════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════ Nacos 服务注册 ═══════════════════════════════════════════════════════════════════

def get_local_ip() -> str:
    """获取本机 IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


_nacos_registry: NacosServiceRegistry = None


def start_nacos_registry():
    """启动 Nacos 服务注册"""
    global _nacos_registry

    nacos_enabled = os.getenv("NACOS_ENABLED", "false").lower() == "true"
    if not nacos_enabled:
        logger.info("[Nacos] 未启用 Nacos 服务注册")
        return

    service_name = os.getenv("NACOS_SERVICE_NAME", "nexus-agent-engine")
    port = int(os.getenv("AGENT_ENGINE_PORT", "8001"))
    ip = os.getenv("SERVICE_IP", get_local_ip())

    _nacos_registry = create_registry(service_name, ip, port)
    _nacos_registry.start()

    logger.info(f"[Nacos] 服务注册完成: {service_name} -> {ip}:{port}")


def stop_nacos_registry():
    """停止 Nacos 服务注册"""
    global _nacos_registry
    if _nacos_registry:
        _nacos_registry.stop()


# ═══════════════════════════════════════════════════════════════════ 应用生命周期 ═══════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时：注册到 Nacos
    start_nacos_registry()

    yield

    # 关闭时：从 Nacos 注销
    stop_nacos_registry()


# ═══════════════════════════════════════════════════════════════════ 应用 ═══════════════════════════════════════════════════════════════════
app = FastAPI(
    title="NexusAgent — Agent Engine",
    version="0.1.0",
    description="Python 核心 AI 服务：LangGraph Agent + 中断控制 + SSE 流式输出",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════════ 路由 ═══════════════════════════════════════════════════════════════════
app.include_router(chat_router, prefix="/api/v1/agent")
app.include_router(control_router, prefix="/api/v1/agent")
app.include_router(websocket_router, prefix="/api/v1/agent")
app.include_router(admin_router, prefix="/api/v1", tags=["admin"])
app.include_router(models_router, prefix="/api/v1", tags=["models"])
app.include_router(media_router, prefix="/api/v1/media")


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """健康检查"""
    return HealthResponse()


# ═══════════════════════════════════════════════════════════════════ 启动 ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from app.config import settings

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.agent_engine_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
