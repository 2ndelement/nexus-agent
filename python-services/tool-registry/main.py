"""
tool-registry FastAPI 应用入口。

端口：8011
数据库：MySQL 127.0.0.1:3306/nexus_agent（user=nexus, pass=nexus_pass）
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.tools import router as tools_router, set_session_factory
from services.tool_service import create_db_engine, get_session_factory, seed_builtin_tools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── 应用创建 ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="NexusAgent Tool Registry",
    description="工具注册中心：负责工具注册、查询与执行分发",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 数据库初始化 ───────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://nexus:nexus_pass@127.0.0.1:3306/nexus_agent?charset=utf8mb4",
)


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("正在初始化数据库连接 url=%s", DATABASE_URL.replace("nexus_pass", "***"))
    try:
        engine = create_db_engine(DATABASE_URL)
        session_factory = get_session_factory(engine)
        set_session_factory(session_factory)

        # 写入内置工具
        with session_factory() as session:
            seed_builtin_tools(session)

        logger.info("tool-registry 服务启动完成，监听端口 8011")
    except Exception as e:
        logger.error("数据库初始化失败: %s，服务将以降级模式启动", e)


# ── 路由注册 ───────────────────────────────────────────────────────────────────

app.include_router(tools_router)


# ── 健康检查 ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "tool-registry"}


# ── 启动入口 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8011, reload=False)
