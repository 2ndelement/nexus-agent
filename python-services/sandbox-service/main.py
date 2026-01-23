"""
main.py — sandbox-service FastAPI 入口

服务端口：8020

功能：
  - POST /execute — 在隔离容器中执行代码
  - GET  /health — 健康检查
  - GET  /docker/ping — 检查 Docker 可用性

安全特性：
  - 网络隔离（容器无法访问外部网络）
  - 资源限制（内存 256MB，CPU 0.5 核）
  - 超时控制（最长 120 秒）
"""
from __future__ import annotations
import logging

import uvicorn

import os
import socket
from common.nacos import create_registry
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.schemas import ExecuteRequest, ExecuteResponse
from app.executor import get_executor

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="NexusAgent Sandbox Service",
    description="隔离容器代码执行服务",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "sandbox-service"}


@app.get("/docker/ping")
async def docker_ping():
    """检查 Docker 是否可用"""
    executor = get_executor()
    ok = await executor.health_check()
    return {"docker_available": ok}


@app.post("/execute", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest):
    """
    在隔离容器中执行代码。
    
    安全措施：
    - 容器网络隔离（禁止访问外网）
    - 内存限制 256MB
    - CPU 限制 0.5 核
    - 超时自动 kill
    """
    executor = get_executor()
    
    try:
        result = await executor.execute(
            code=req.code,
            language=req.language,
            timeout=req.timeout,
        )
        
        return ExecuteResponse(
            success=result.success,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            duration_ms=result.duration_ms,
            error=result.error,
        )
        
    except Exception as e:
        logger.exception("执行异常")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":

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
    
    service_name = os.getenv("NACOS_SERVICE_NAME", "nexus-sandbox-service")
    port = int(os.getenv("PORT", "8000"))
    ip = os.getenv("SERVICE_IP", get_local_ip())
    
    registry = create_registry(service_name, ip, port)
    registry.start()
    print(f"[Nacos] 服务注册完成: {service_name} -> {ip}:{port}")

# 启动时注册
start_nacos_registry()

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
