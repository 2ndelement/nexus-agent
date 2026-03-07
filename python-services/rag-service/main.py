"""
main.py — RAG Service FastAPI 应用入口
端口：8013
"""
from __future__ import annotations

import logging
import os
import socket

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
logger = logging.getLogger(__name__)

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


@app.on_event("startup")
async def warmup_models():
    """启动时预热（后台线程）"""
    import threading
    from app.config import settings

    def _warmup():
        if settings.use_embed_service:
            # 使用远程 Embed Service，检查连接
            logger.info(f"[Warmup] 检查 Embed Service 连接: {settings.embed_service_url}")
            try:
                import httpx
                response = httpx.get(f"{settings.embed_service_url}/health", timeout=10.0)
                response.raise_for_status()
                logger.info("[Warmup] Embed Service 连接正常")
            except Exception as e:
                logger.warning(f"[Warmup] Embed Service 连接失败: {e}")
        else:
            # 使用本地模型，预热
            logger.info("[Warmup] 预热本地 Embedding 模型...")
            try:
                from app.embedder import get_embedder
                embedder = get_embedder()
                embedder.embed_query("warmup")
                logger.info("[Warmup] Embedding 模型预热完成")
            except Exception as e:
                logger.warning(f"[Warmup] Embedding 模型预热失败: {e}")

        logger.info("[Warmup] 预热 Retriever...")
        try:
            from app.dependencies import get_milvus_retriever
            get_milvus_retriever()
            logger.info("[Warmup] Retriever 预热完成")
        except Exception as e:
            logger.warning(f"[Warmup] Retriever 预热失败: {e}")

    threading.Thread(target=_warmup, daemon=True).start()
    logger.info("[Warmup] 后台预热已启动")

# 注册路由（都挂在 /api/v1/knowledge 下）
app.include_router(knowledge_router, prefix="/api/v1/knowledge", tags=["knowledge"])
app.include_router(retrieve_router, prefix="/api/v1/knowledge", tags=["retrieve"])


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    return HealthResponse()


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
        service_name = os.getenv("NACOS_SERVICE_NAME", "nexus-rag-service")
        port = int(os.getenv("PORT", "8013"))
        ip = os.getenv("SERVICE_IP", get_local_ip())

        registry = create_registry(service_name, ip, port)
        registry.start()
        logger.info(f"[Nacos] 服务注册完成: {service_name} -> {ip}:{port}")
        return registry
    except Exception as e:
        logger.warning(f"[Nacos] 服务注册失败: {e}")
        return None


if __name__ == "__main__":
    from app.config import settings

    # 启动时注册
    _nacos_registry = start_nacos_registry()

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.rag_service_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
