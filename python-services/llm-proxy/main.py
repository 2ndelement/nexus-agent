"""
main.py — LLM Proxy FastAPI 应用入口

服务端口：8010
"""
from __future__ import annotations

import logging
import os
import socket

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.completions import router as completions_router
from app.api.v1.stats import router as stats_router
from app.schemas import HealthResponse

# ─────────────────────────── 日志 ───────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────── 应用 ───────────────────────────
app = FastAPI(
    title="NexusAgent — LLM Proxy",
    version="0.1.0",
    description=(
        "LLM 统一代理服务：OpenAI 协议兼容 · 多模型路由 · Token 统计\n\n"
        "默认模型：`MiniMax-M2.5-highspeed`（base_url: https://copilot.lab.2ndelement.tech/v1）"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS（开发环境宽松，生产由 Gateway 控制）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────── 路由 ───────────────────────────
app.include_router(completions_router, prefix="/v1", tags=["completions"])
app.include_router(stats_router, prefix="/v1", tags=["stats"])


@app.on_event("shutdown")
async def shutdown_event():
    """优雅停机：关闭连接池。"""
    from app.core.router import get_client_pool
    await get_client_pool().close_all()
    logger.info("LLM Proxy 已关闭")


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """健康检查接口，供 K8s/Docker 探针使用。"""
    return HealthResponse()


@app.get("/v1/models", tags=["meta"], summary="列出已配置的模型")
async def list_models() -> dict:
    """返回当前 proxy 配置的所有模型名称列表。"""
    from app.config import settings
    return {
        "object": "list",
        "data": [
            {"id": m, "object": "model", "owned_by": "llm-proxy"}
            for m in settings.list_models()
        ],
    }


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
        logger.info("[Nacos] 未启用 Nacos 服务注册")
        return None

    try:
        from common.nacos import create_registry
        service_name = os.getenv("NACOS_SERVICE_NAME", "nexus-llm-proxy")
        port = int(os.getenv("PORT", "8010"))
        ip = os.getenv("SERVICE_IP", get_local_ip())

        registry = create_registry(service_name, ip, port)
        registry.start()
        logger.info(f"[Nacos] 服务注册完成: {service_name} -> {ip}:{port}")
        return registry
    except Exception as e:
        logger.warning(f"[Nacos] 服务注册失败: {e}")
        return None


# ─────────────────────────── 启动 ───────────────────────────
if __name__ == "__main__":
    from app.config import settings

    # 启动时注册
    _nacos_registry = start_nacos_registry()

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.llm_proxy_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
