"""
tools 路由模块。

API 接口：
  GET    /api/tools                  列出可用工具（多租户隔离）
  GET    /api/tools/{name}           获取工具详情
  POST   /api/tools                  注册工具（幂等）
  DELETE /api/tools/{name}           删除工具（仅租户自定义工具）
  POST   /api/tools/execute          执行工具
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from models import (
    ApiResponse,
    ExecuteToolRequest,
    ExecuteToolResponse,
    RegisterToolRequest,
    ToolResponse,
)
from services.tool_service import ToolService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


# ── 依赖注入 ──────────────────────────────────────────────────────────────────

# 全局 Session 工厂，由 main.py 启动时注入
_session_factory = None


def set_session_factory(factory) -> None:
    global _session_factory
    _session_factory = factory


def get_db() -> Session:
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized")
    db = _session_factory()
    try:
        yield db
    finally:
        db.close()


def get_service(db: Session = Depends(get_db)) -> ToolService:
    return ToolService(db)


def _parse_tenant_id(x_tenant_id: Optional[str]) -> Optional[int]:
    if x_tenant_id is None:
        return None
    try:
        return int(x_tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="X-Tenant-Id 必须是整数")


# ── 路由实现 ──────────────────────────────────────────────────────────────────

@router.get("", response_model=ApiResponse)
def list_tools(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
    service: ToolService = Depends(get_service),
):
    """
    列出可用工具。
    - 内置工具（calculator、web_search）对所有请求可见
    - 租户自定义工具仅对指定租户可见（通过 X-Tenant-Id Header 传递）
    """
    tenant_id = _parse_tenant_id(x_tenant_id)
    tools = service.list_tools(tenant_id)
    return ApiResponse.success([t.model_dump() for t in tools])


@router.get("/{name}", response_model=ApiResponse)
def get_tool(
    name: str,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
    service: ToolService = Depends(get_service),
):
    """获取工具详情"""
    tenant_id = _parse_tenant_id(x_tenant_id)
    tool = service.get_tool(name, tenant_id)
    if tool is None:
        return ApiResponse.fail(404, f"工具 '{name}' 不存在")
    return ApiResponse.success(tool.model_dump())


@router.post("", response_model=ApiResponse)
def register_tool(
    req: RegisterToolRequest,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
    service: ToolService = Depends(get_service),
    db: Session = Depends(get_db),
):
    """
    注册工具（幂等：同名工具存在则更新）。
    内置工具（scope=BUILTIN）无需 X-Tenant-Id。
    租户工具（scope=TENANT）需要 X-Tenant-Id。
    """
    from models import ToolScope
    tenant_id = _parse_tenant_id(x_tenant_id)
    if req.scope == ToolScope.TENANT and tenant_id is None:
        return ApiResponse.fail(400, "注册租户工具时必须提供 X-Tenant-Id")

    tool = service.register_tool(req, tenant_id)
    db.commit()
    return ApiResponse.success(tool.model_dump())


@router.delete("/{name}", response_model=ApiResponse)
def delete_tool(
    name: str,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
    service: ToolService = Depends(get_service),
    db: Session = Depends(get_db),
):
    """删除租户自定义工具"""
    tenant_id = _parse_tenant_id(x_tenant_id)
    if tenant_id is None:
        return ApiResponse.fail(400, "删除工具时必须提供 X-Tenant-Id")

    try:
        deleted = service.delete_tool(name, tenant_id)
    except PermissionError as e:
        return ApiResponse.fail(403, str(e))

    if not deleted:
        return ApiResponse.fail(404, f"工具 '{name}' 不存在")

    db.commit()
    return ApiResponse.success({"deleted": name})


@router.post("/execute", response_model=ApiResponse)
async def execute_tool(
    req: ExecuteToolRequest,
    service: ToolService = Depends(get_service),
):
    """
    执行工具。

    请求体中可选提供 tenant_id 用于工具查找隔离。
    执行失败时返回 success=False + error 信息，HTTP 状态码仍为 200。
    """
    result = await service.execute_tool(req)
    return ApiResponse.success(result.model_dump())
