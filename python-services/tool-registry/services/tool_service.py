"""
tool-registry 工具服务层。

负责：
1. 工具注册（写入 MySQL 元数据，幂等处理）
2. 工具查询（支持多租户隔离：内置工具全局可见，租户工具仅本租户可见）
3. 工具执行分发（内置工具直接调用，扩展点支持自定义工具）
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from builtin_tools import calculator, web_search, sandbox
from models import (
    ApiResponse,
    ExecuteToolRequest,
    ExecuteToolResponse,
    ParameterSchema,
    RegisterToolRequest,
    ToolDefinition,
    ToolResponse,
    ToolScope,
    ToolStatus,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# SQLAlchemy ORM
# ──────────────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class ToolORM(Base):
    __tablename__ = "tool_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, nullable=True)       # NULL = 内置全局工具
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    parameters_schema = Column(Text, nullable=False)  # JSON string
    scope = Column(String(20), nullable=False, default="TENANT")
    status = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ──────────────────────────────────────────────────────────────────────────────
# 内置工具注册表（name → 执行函数）
# ──────────────────────────────────────────────────────────────────────────────

_BUILTIN_EXECUTORS: Dict[str, Any] = {
    "calculator": calculator.calculate,
    "sandbox_execute": sandbox.execute_code,
    "web_search": web_search.web_search,
}

_BUILTIN_DEFINITIONS = [
    calculator.TOOL_DEFINITION,
    sandbox.TOOL_DEFINITION,
    web_search.TOOL_DEFINITION,
]


# ──────────────────────────────────────────────────────────────────────────────
# 服务类
# ──────────────────────────────────────────────────────────────────────────────

class ToolService:
    """
    工具服务。
    数据库会话由调用方注入（依赖注入），方便单元测试 Mock。
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ── 注册工具 ──────────────────────────────────────────────────────────────

    def register_tool(
        self,
        req: RegisterToolRequest,
        tenant_id: Optional[int] = None,
    ) -> ToolResponse:
        """
        注册工具（幂等：同一 tenant_id + name 已存在则更新）。

        内置工具（scope=BUILTIN）tenant_id 为 None，全局可见。
        租户工具（scope=TENANT）需指定 tenant_id。
        """
        params_json = req.tool.parameters.model_dump_json()

        # 查询是否已存在
        existing = self._find_by_name(tenant_id, req.tool.name)
        if existing:
            existing.description = req.tool.description
            existing.parameters_schema = params_json
            existing.scope = req.scope.value
            existing.updated_at = datetime.utcnow()
            self._db.flush()
            logger.info("更新工具 name=%s tenant_id=%s", req.tool.name, tenant_id)
            return self._to_response(existing)

        orm = ToolORM(
            tenant_id=tenant_id,
            name=req.tool.name,
            description=req.tool.description,
            parameters_schema=params_json,
            scope=req.scope.value,
            status=ToolStatus.ENABLED.value,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self._db.add(orm)
        self._db.flush()
        logger.info("注册工具 name=%s tenant_id=%s", req.tool.name, tenant_id)
        return self._to_response(orm)

    # ── 查询工具列表 ──────────────────────────────────────────────────────────

    def list_tools(self, tenant_id: Optional[int] = None) -> List[ToolResponse]:
        """
        列出可用工具：
        - 内置工具（tenant_id IS NULL, scope=BUILTIN）：所有请求可见
        - 租户工具（scope=TENANT）：仅本租户可见
        """
        from sqlalchemy import or_, and_

        query = self._db.query(ToolORM).filter(
            ToolORM.status == ToolStatus.ENABLED.value,
            or_(
                ToolORM.scope == ToolScope.BUILTIN.value,          # 内置工具全局可见
                and_(
                    ToolORM.scope == ToolScope.TENANT.value,
                    ToolORM.tenant_id == tenant_id,                # 租户自定义工具
                )
            )
        )
        records = query.all()
        return [self._to_response(r) for r in records]

    # ── 查询单个工具 ──────────────────────────────────────────────────────────

    def get_tool(self, name: str, tenant_id: Optional[int] = None) -> Optional[ToolResponse]:
        """
        根据名称查询工具，先查租户自定义，再查内置。
        """
        # 优先查租户自定义工具
        if tenant_id is not None:
            orm = self._find_by_name(tenant_id, name)
            if orm:
                return self._to_response(orm)

        # 再查内置工具
        orm = self._db.query(ToolORM).filter(
            ToolORM.name == name,
            ToolORM.tenant_id.is_(None),
            ToolORM.status == ToolStatus.ENABLED.value,
        ).first()
        if orm:
            return self._to_response(orm)
        return None

    # ── 删除工具 ──────────────────────────────────────────────────────────────

    def delete_tool(self, name: str, tenant_id: int) -> bool:
        """
        删除租户自定义工具（内置工具不允许删除）。
        返回 True 表示删除成功，False 表示工具不存在。
        """
        # 先检查是否为内置工具（以防租户尝试删除内置工具）
        builtin = self._db.query(ToolORM).filter(
            ToolORM.name == name,
            ToolORM.tenant_id.is_(None),
            ToolORM.scope == ToolScope.BUILTIN.value,
        ).first()
        if builtin:
            raise PermissionError("内置工具不允许删除")

        orm = self._find_by_name(tenant_id, name)
        if not orm:
            return False
        self._db.delete(orm)
        self._db.flush()
        return True

    # ── 执行工具 ──────────────────────────────────────────────────────────────

    async def execute_tool(self, req: ExecuteToolRequest) -> ExecuteToolResponse:
        """
        执行工具。

        优先级：租户自定义工具 > 内置工具。
        内置工具通过 _BUILTIN_EXECUTORS 直接调用。
        """
        tool_name = req.name

        # 检查工具是否存在（权限校验）
        tool_resp = self.get_tool(tool_name, req.tenant_id)
        if tool_resp is None:
            return ExecuteToolResponse(
                tool_name=tool_name,
                result=None,
                success=False,
                error=f"工具 '{tool_name}' 不存在或无权访问",
            )

        # 执行内置工具
        if tool_name in _BUILTIN_EXECUTORS:
            try:
                executor = _BUILTIN_EXECUTORS[tool_name]
                import asyncio, inspect
                if inspect.iscoroutinefunction(executor):
                    result = await executor(**req.arguments)
                else:
                    result = executor(**req.arguments)
                return ExecuteToolResponse(
                    tool_name=tool_name,
                    result=result,
                    success=True,
                )
            except (ValueError, TypeError, ZeroDivisionError) as e:
                logger.warning("工具执行失败 name=%s error=%s", tool_name, e)
                return ExecuteToolResponse(
                    tool_name=tool_name,
                    result=None,
                    success=False,
                    error=str(e),
                )

        # 自定义工具（暂不支持，预留扩展点）
        return ExecuteToolResponse(
            tool_name=tool_name,
            result=None,
            success=False,
            error=f"自定义工具 '{tool_name}' 执行器未注册",
        )

    # ── 私有辅助 ──────────────────────────────────────────────────────────────

    def _find_by_name(self, tenant_id: Optional[int], name: str) -> Optional[ToolORM]:
        """查询指定 tenant_id + name 的工具记录"""
        q = self._db.query(ToolORM).filter(ToolORM.name == name)
        if tenant_id is None:
            q = q.filter(ToolORM.tenant_id.is_(None))
        else:
            q = q.filter(ToolORM.tenant_id == tenant_id)
        return q.first()

    def _to_response(self, orm: ToolORM) -> ToolResponse:
        try:
            params_dict = json.loads(orm.parameters_schema)
            params = ParameterSchema(**params_dict)
        except (json.JSONDecodeError, Exception):
            params = ParameterSchema()
        return ToolResponse(
            id=orm.id,
            tenant_id=orm.tenant_id,
            name=orm.name,
            description=orm.description,
            parameters=params,
            scope=ToolScope(orm.scope),
            status=ToolStatus(orm.status),
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )


# ──────────────────────────────────────────────────────────────────────────────
# 数据库工厂
# ──────────────────────────────────────────────────────────────────────────────

def create_db_engine(database_url: str):
    """创建 SQLAlchemy Engine"""
    engine = create_engine(database_url, echo=False, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return engine


def get_session_factory(engine):
    """创建 Session 工厂"""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def seed_builtin_tools(session: Session) -> None:
    """
    在服务启动时将内置工具定义写入数据库（幂等）。
    确保 calculator 和 web_search 始终可用。
    """
    service = ToolService(session)
    for tool_def in _BUILTIN_DEFINITIONS:
        req = RegisterToolRequest(
            tool=ToolDefinition(
                name=tool_def["name"],
                description=tool_def["description"],
                parameters=ParameterSchema(**tool_def["parameters"]),
            ),
            scope=ToolScope.BUILTIN,
        )
        service.register_tool(req, tenant_id=None)
    session.commit()
    logger.info("内置工具初始化完成，共 %d 个", len(_BUILTIN_DEFINITIONS))
