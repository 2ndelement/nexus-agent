"""
memory-service FastAPI 应用入口

端口：8012
"""
from __future__ import annotations

import logging
import os

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8012, reload=False)
