"""
main.py — sandbox-service FastAPI 入口

服务端口：8020

V5 更新：
  - 支持会话绑定容器（同一会话复用容器）
  - 支持工作区隔离（不同用户/组织文件隔离）
  - 新增工作区文件管理 API

功能：
  - POST /execute — 在隔离容器中执行代码
  - GET  /health — 健康检查
  - GET  /docker/ping — 检查 Docker 可用性
  - GET  /pool/status — 容器池状态
  - GET  /sessions — 活跃会话列表
  - GET  /workspace/{owner_type}/{owner_id}/{conversation_id} — 工作区文件列表
  - GET  /workspace/{owner_type}/{owner_id}/{conversation_id}/{filename} — 下载文件
  - DELETE /workspace/{owner_type}/{owner_id}/{conversation_id} — 清理工作区

安全特性：
  - 网络隔离（容器无法访问外部网络）
  - 资源限制（内存 256MB，CPU 0.5 核）
  - 超时控制（最长 120 秒）
  - 工作区隔离（不同用户/组织文件互不可见）
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import socket
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import settings
from app.schemas import (
    ExecuteRequest,
    ExecuteResponse,
    WorkspaceFile,
    WorkspaceListResponse,
)

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# 工作区根目录
WORKSPACE_ROOT = os.getenv("SANDBOX_WORKSPACE_ROOT", "/data/sandbox")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 确保工作区根目录存在
    os.makedirs(WORKSPACE_ROOT, exist_ok=True)
    logger.info(f"[Startup] 工作区根目录: {WORKSPACE_ROOT}")

    # 启动时：初始化会话管理器
    logger.info("[Startup] 开始初始化会话管理器...")
    try:
        from app.executor.session_manager import init_session_manager
        count = await init_session_manager()
        logger.info(f"[Startup] 会话管理器初始化完成，预热了 {count} 个容器")
    except Exception as e:
        logger.warning(f"[Startup] 会话管理器初始化失败: {e}")

    yield

    # 关闭时：清理会话管理器
    logger.info("[Shutdown] 关闭会话管理器...")
    try:
        from app.executor.session_manager import close_session_manager
        await close_session_manager()
        logger.info("[Shutdown] 会话管理器已关闭")
    except Exception as e:
        logger.warning(f"[Shutdown] 会话管理器关闭失败: {e}")


app = FastAPI(
    title="NexusAgent Sandbox Service",
    description="隔离容器代码执行服务（V5：支持会话隔离）",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════
# 健康检查 API
# ═══════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "sandbox-service", "version": "2.0.0"}


@app.get("/docker/ping")
async def docker_ping():
    """检查 Docker 是否可用"""
    try:
        import aiodocker
        docker = aiodocker.Docker()
        await docker.ping()
        await docker.close()
        return {"docker_available": True}
    except Exception as e:
        logger.warning(f"Docker ping failed: {e}")
        return {"docker_available": False, "error": str(e)}


@app.get("/pool/status")
async def pool_status():
    """获取容器池状态"""
    try:
        from app.executor.session_manager import get_session_manager
        manager = get_session_manager()
        return {
            "enabled": True,
            "active_sessions": manager.active_session_count,
            "warm_pool_size": manager.warm_pool_size,
            "max_sessions": manager.max_sessions,
            "idle_timeout": manager.idle_timeout,
        }
    except Exception as e:
        return {
            "enabled": False,
            "error": str(e),
        }


@app.get("/sessions")
async def list_sessions():
    """列出活跃会话"""
    try:
        from app.executor.session_manager import get_session_manager
        manager = get_session_manager()

        sessions = []
        for key, session in manager._active_sessions.items():
            sessions.append({
                "session_key": key,
                "container_id": session.container.id[:12],
                "workspace_path": session.workspace_path,
                "created_at": datetime.fromtimestamp(session.created_at).isoformat(),
                "last_access": datetime.fromtimestamp(session.last_access).isoformat(),
                "execution_count": session.execution_count,
            })

        return {
            "total": len(sessions),
            "sessions": sessions,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# 代码执行 API
# ═══════════════════════════════════════════════════════════════════

@app.post("/execute", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest):
    """
    在隔离容器中执行代码。

    V5 新增：
    - 支持 owner_type/owner_id/conversation_id 实现会话隔离
    - 同一会话复用容器，保持文件状态
    - 返回工作区文件列表

    安全措施：
    - 容器网络隔离（禁止访问外网）
    - 内存限制 256MB
    - CPU 限制 0.5 核
    - 超时自动 kill
    """
    # 如果没有提供会话信息，使用旧版执行器
    if not req.owner_id or not req.conversation_id:
        return await _execute_legacy(req)

    # 使用会话管理器执行
    try:
        from app.executor.session_manager import get_session_manager

        manager = get_session_manager()

        # 获取或创建会话
        session = await manager.get_or_create_session(
            owner_type=req.owner_type,
            owner_id=req.owner_id,
            conversation_id=req.conversation_id,
        )

        # 执行代码
        result = await manager.execute_in_session(
            session=session,
            code=req.code,
            language=req.language,
            timeout=min(req.timeout, settings.max_timeout),
        )

        return ExecuteResponse(
            success=result["success"],
            stdout=result["stdout"],
            stderr=result["stderr"],
            exit_code=result["exit_code"],
            duration_ms=result["duration_ms"],
            error=result.get("error"),
            workspace_files=result.get("workspace_files", []),
            session_id=result.get("session_id"),
        )

    except Exception as e:
        logger.exception("执行异常")
        raise HTTPException(status_code=500, detail=str(e))


async def _execute_legacy(req: ExecuteRequest) -> ExecuteResponse:
    """旧版执行逻辑（无会话隔离，兼容旧 API）"""
    from app.executor import get_executor

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


# ═══════════════════════════════════════════════════════════════════
# 工作区文件管理 API
# ═══════════════════════════════════════════════════════════════════

@app.get("/workspace/{owner_type}/{owner_id}/{conversation_id}")
async def list_workspace_files(
    owner_type: str,
    owner_id: str,
    conversation_id: str,
):
    """
    列出工作区文件。

    路径格式：/workspace/{owner_type}/{owner_id}/{conversation_id}
    示例：/workspace/PERSONAL/17/conv_abc123
    """
    workspace_path = os.path.join(WORKSPACE_ROOT, owner_type, owner_id, conversation_id)

    if not os.path.exists(workspace_path):
        return WorkspaceListResponse(
            files=[],
            total_size=0,
            workspace_path=workspace_path,
        )

    files = []
    total_size = 0

    try:
        for item in Path(workspace_path).iterdir():
            stat = item.stat()
            size = stat.st_size if item.is_file() else 0
            total_size += size

            files.append(WorkspaceFile(
                name=item.name,
                size=size,
                modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                is_dir=item.is_dir(),
            ))

        return WorkspaceListResponse(
            files=files,
            total_size=total_size,
            workspace_path=workspace_path,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workspace/{owner_type}/{owner_id}/{conversation_id}/{filename:path}")
async def download_workspace_file(
    owner_type: str,
    owner_id: str,
    conversation_id: str,
    filename: str,
):
    """
    下载工作区文件。

    路径格式：/workspace/{owner_type}/{owner_id}/{conversation_id}/{filename}
    示例：/workspace/PERSONAL/17/conv_abc123/data.csv
    """
    workspace_path = os.path.join(WORKSPACE_ROOT, owner_type, owner_id, conversation_id)
    file_path = os.path.join(workspace_path, filename)

    # 安全检查：防止路径遍历攻击
    try:
        real_workspace = os.path.realpath(workspace_path)
        real_file = os.path.realpath(file_path)
        if not real_file.startswith(real_workspace):
            raise HTTPException(status_code=403, detail="Access denied")
    except Exception:
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=400, detail="Not a file")

    return FileResponse(
        path=file_path,
        filename=os.path.basename(filename),
    )


@app.delete("/workspace/{owner_type}/{owner_id}/{conversation_id}")
async def delete_workspace(
    owner_type: str,
    owner_id: str,
    conversation_id: str,
):
    """
    删除工作区。

    警告：此操作不可逆，会删除工作区内所有文件。
    """
    workspace_path = os.path.join(WORKSPACE_ROOT, owner_type, owner_id, conversation_id)

    if not os.path.exists(workspace_path):
        return {"deleted": False, "reason": "Workspace not found"}

    try:
        shutil.rmtree(workspace_path)
        logger.info(f"删除工作区: {workspace_path}")
        return {"deleted": True, "path": workspace_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# Nacos 服务注册
# ═══════════════════════════════════════════════════════════════════

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
        service_name = os.getenv("NACOS_SERVICE_NAME", "nexus-sandbox-service")
        port = int(os.getenv("PORT", "8020"))
        ip = os.getenv("SERVICE_IP", get_local_ip())

        registry = create_registry(service_name, ip, port)
        registry.start()
        logger.info(f"[Nacos] 服务注册完成: {service_name} -> {ip}:{port}")
        return registry
    except Exception as e:
        logger.warning(f"[Nacos] 服务注册失败: {e}")
        return None


if __name__ == "__main__":
    # 启动时注册
    _nacos_registry = start_nacos_registry()

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
