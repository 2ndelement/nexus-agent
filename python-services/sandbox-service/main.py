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
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
