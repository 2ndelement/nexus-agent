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
    
    service_name = os.getenv("NACOS_SERVICE_NAME", "nexus-tool-registry")
    port = int(os.getenv("PORT", "8000"))
    ip = os.getenv("SERVICE_IP", get_local_ip())
    
    registry = create_registry(service_name, ip, port)
    registry.start()
    print(f"[Nacos] 服务注册完成: {service_name} -> {ip}:{port}")

# 启动时注册
start_nacos_registry()

    uvicorn.run("main:app", host="0.0.0.0", port=8011, reload=False)
