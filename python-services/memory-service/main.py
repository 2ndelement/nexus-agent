"""
memory-service FastAPI 应用入口

端口：8012
"""
from __future__ import annotations

import logging
import os
import socket

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models import Base
from routers.memory import router as memory_router

# ─── 日志 ─────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ─── 数据库配置 ───────────────────────────────────────────────────────────────
DB_URL = os.getenv(
    "DATABASE_URL",
    "mysql+aiomysql://nexus:nexus_pass@127.0.0.1:3306/nexus_agent",
)

engine = create_async_engine(DB_URL, echo=False, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# ─── FastAPI 应用 ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="NexusAgent Memory Service",
    description="长期记忆存储与检索服务（多租户隔离）",
    version="1.0.0",
)

app.include_router(memory_router)


@app.on_event("startup")
async def startup():
    """创建数据库表（幂等）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("memory-service 启动完成，端口 8012")


@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "memory-service"}


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
        service_name = os.getenv("NACOS_SERVICE_NAME", "nexus-memory-service")
        port = int(os.getenv("PORT", "8012"))
        ip = os.getenv("SERVICE_IP", get_local_ip())

        registry = create_registry(service_name, ip, port)
        registry.start()
        logger.info(f"[Nacos] 服务注册完成: {service_name} -> {ip}:{port}")
        return registry
    except Exception as e:
        logger.warning(f"[Nacos] 服务注册失败: {e}")
        return None


if __name__ == "__main__":
    import uvicorn

    # 启动时注册
    _nacos_registry = start_nacos_registry()

    uvicorn.run("main:app", host="0.0.0.0", port=8012, reload=False)
