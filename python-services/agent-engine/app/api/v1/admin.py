"""
app/api/v1/admin.py — 管理接口

提供租户、用户、Agent 的 CRUD 操作
用于前端管理界面

V5 更新：
- Agent API 支持 X-Context Header（personal 或 org:{code}）
- 兼容旧版 tenant_id 查询参数
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import get_db_connection

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_context_header(x_context: Optional[str], x_user_id: Optional[str], tenant_id: Optional[int]) -> tuple[str, str]:
    """
    解析 X-Context Header，返回 (owner_type, owner_id)。

    V5 格式：
    - "personal" -> ("PERSONAL", user_id)
    - "org:{code}" -> ("ORGANIZATION", code)

    兼容旧版：
    - 如果有 tenant_id 参数，转换为 ("ORGANIZATION", str(tenant_id))
    """
    if x_context:
        if x_context == "personal":
            return ("PERSONAL", x_user_id or "")
        elif x_context.startswith("org:"):
            org_code = x_context[4:]
            return ("ORGANIZATION", org_code)
        else:
            return ("ORGANIZATION", x_context)
    elif tenant_id is not None:
        # 兼容旧版 tenant_id 查询参数
        return ("ORGANIZATION", str(tenant_id))
    else:
        # 默认个人空间
        return ("PERSONAL", x_user_id or "")


# ============================================================================
# Request/Response Models
# ============================================================================

class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=50)
    status: int = 1
    config: Optional[dict] = None


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    status: Optional[int] = None
    config: Optional[dict] = None


class TenantResponse(BaseModel):
    id: int
    name: str
    code: str
    status: int
    config: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UserCreate(BaseModel):
    tenant_id: int
    username: str = Field(..., min_length=1, max_length=100)
    nickname: Optional[str] = None
    email: Optional[str] = None
    status: int = 1


class UserResponse(BaseModel):
    id: int
    tenant_id: int
    username: str
    nickname: Optional[str] = None
    email: Optional[str] = None
    status: int
    created_at: Optional[str] = None


class AgentCreate(BaseModel):
    tenant_id: Optional[int] = None  # V5: 可选，优先使用 X-Context Header
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 4096
    tools_enabled: Optional[str] = None
    knowledge_base_ids: Optional[str] = None
    status: int = 1


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools_enabled: Optional[str] = None
    knowledge_base_ids: Optional[str] = None
    status: Optional[int] = None


class AgentResponse(BaseModel):
    id: int
    tenant_id: int
    name: str
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model: str
    temperature: float
    max_tokens: int
    tools_enabled: Optional[str] = None
    status: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ApiResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: Optional[Any] = None


# ============================================================================
# Tenant APIs
# ============================================================================

@router.get("/tenants", response_model=ApiResponse)
async def list_tenants():
    """列出所有租户"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM tenant ORDER BY id")
            rows = cursor.fetchall()
            tenants = []
            for row in rows:
                tenant = dict(row)
                if tenant.get('config') and isinstance(tenant['config'], str):
                    try:
                        tenant['config'] = json.loads(tenant['config'])
                    except:
                        pass
                if tenant.get('created_at'):
                    tenant['created_at'] = str(tenant['created_at'])
                if tenant.get('updated_at'):
                    tenant['updated_at'] = str(tenant['updated_at'])
                tenants.append(tenant)
            return ApiResponse(data=tenants)
    finally:
        conn.close()


@router.post("/tenants", response_model=ApiResponse)
async def create_tenant(body: TenantCreate):
    """创建租户"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check if code exists
            cursor.execute("SELECT id FROM tenant WHERE code = %s", (body.code,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="租户代码已存在")

            config_str = json.dumps(body.config) if body.config else None
            cursor.execute(
                """
                INSERT INTO tenant (name, code, status, config)
                VALUES (%s, %s, %s, %s)
                """,
                (body.name, body.code, body.status, config_str)
            )
            conn.commit()
            tenant_id = cursor.lastrowid

            cursor.execute("SELECT * FROM tenant WHERE id = %s", (tenant_id,))
            row = cursor.fetchone()
            tenant = dict(row)
            if tenant.get('created_at'):
                tenant['created_at'] = str(tenant['created_at'])
            if tenant.get('updated_at'):
                tenant['updated_at'] = str(tenant['updated_at'])

            return ApiResponse(data=tenant)
    finally:
        conn.close()


@router.put("/tenants/{tenant_id}", response_model=ApiResponse)
async def update_tenant(tenant_id: int, body: TenantUpdate):
    """更新租户"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            updates = []
            values = []

            if body.name is not None:
                updates.append("name = %s")
                values.append(body.name)
            if body.code is not None:
                updates.append("code = %s")
                values.append(body.code)
            if body.status is not None:
                updates.append("status = %s")
                values.append(body.status)
            if body.config is not None:
                updates.append("config = %s")
                values.append(json.dumps(body.config))

            if not updates:
                raise HTTPException(status_code=400, detail="没有要更新的字段")

            values.append(tenant_id)
            cursor.execute(
                f"UPDATE tenant SET {', '.join(updates)} WHERE id = %s",
                values
            )
            conn.commit()

            cursor.execute("SELECT * FROM tenant WHERE id = %s", (tenant_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="租户不存在")

            tenant = dict(row)
            if tenant.get('created_at'):
                tenant['created_at'] = str(tenant['created_at'])
            if tenant.get('updated_at'):
                tenant['updated_at'] = str(tenant['updated_at'])

            return ApiResponse(data=tenant)
    finally:
        conn.close()


@router.delete("/tenants/{tenant_id}", response_model=ApiResponse)
async def delete_tenant(tenant_id: int):
    """删除租户"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))
            conn.commit()
            return ApiResponse(data={"deleted": tenant_id})
    finally:
        conn.close()


# ============================================================================
# User APIs
# ============================================================================

@router.get("/users", response_model=ApiResponse)
async def list_users(tenant_id: int = Query(...)):
    """列出租户下的用户"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM user WHERE tenant_id = %s ORDER BY id",
                (tenant_id,)
            )
            rows = cursor.fetchall()
            users = []
            for row in rows:
                user = dict(row)
                if user.get('created_at'):
                    user['created_at'] = str(user['created_at'])
                if user.get('updated_at'):
                    user['updated_at'] = str(user['updated_at'])
                users.append(user)
            return ApiResponse(data=users)
    finally:
        conn.close()


@router.post("/users", response_model=ApiResponse)
async def create_user(body: UserCreate):
    """创建用户"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check if username exists in tenant
            cursor.execute(
                "SELECT id FROM user WHERE tenant_id = %s AND username = %s",
                (body.tenant_id, body.username)
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="用户名已存在")

            cursor.execute(
                """
                INSERT INTO user (tenant_id, username, nickname, email, status)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (body.tenant_id, body.username, body.nickname, body.email, body.status)
            )
            conn.commit()
            user_id = cursor.lastrowid

            cursor.execute("SELECT * FROM user WHERE id = %s", (user_id,))
            row = cursor.fetchone()
            user = dict(row)
            if user.get('created_at'):
                user['created_at'] = str(user['created_at'])

            return ApiResponse(data=user)
    finally:
        conn.close()


# ============================================================================
# Agent APIs
# ============================================================================

@router.get("/agents", response_model=ApiResponse)
async def list_agents(
    tenant_id: Optional[int] = Query(None),
    x_context: Optional[str] = Header(None, alias="X-Context"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    """
    列出 Agent 列表。

    V5 更新：
    - 支持 X-Context Header（personal 或 org:{code}）
    - 兼容旧版 tenant_id 查询参数
    """
    owner_type, owner_id = _parse_context_header(x_context, x_user_id, tenant_id)
    logger.info(f"[ListAgents] owner_type={owner_type}, owner_id={owner_id}")

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # V5: 数据库表暂未添加 owner_type/owner_id 列
            # 当前使用 tenant_id 字段存储 owner_id
            # 个人空间: tenant_id = user_id
            # 组织空间: tenant_id = org_code 或 org_id
            cursor.execute(
                """SELECT * FROM agent_config
                   WHERE tenant_id = %s
                   ORDER BY id""",
                (owner_id,)
            )
            rows = cursor.fetchall()
            agents = []
            for row in rows:
                agent = dict(row)
                if agent.get('created_at'):
                    agent['created_at'] = str(agent['created_at'])
                if agent.get('updated_at'):
                    agent['updated_at'] = str(agent['updated_at'])
                if agent.get('temperature'):
                    agent['temperature'] = float(agent['temperature'])
                agents.append(agent)
            return ApiResponse(data=agents)
    finally:
        conn.close()


@router.get("/agents/{agent_id}", response_model=ApiResponse)
async def get_agent(agent_id: int):
    """获取 Agent 详情"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM agent_config WHERE id = %s", (agent_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Agent 不存在")

            agent = dict(row)
            if agent.get('created_at'):
                agent['created_at'] = str(agent['created_at'])
            if agent.get('updated_at'):
                agent['updated_at'] = str(agent['updated_at'])
            if agent.get('temperature'):
                agent['temperature'] = float(agent['temperature'])

            return ApiResponse(data=agent)
    finally:
        conn.close()


@router.post("/agents", response_model=ApiResponse)
async def create_agent(
    body: AgentCreate,
    x_context: Optional[str] = Header(None, alias="X-Context"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    """
    创建 Agent。

    V5 更新：
    - 支持 X-Context Header（personal 或 org:{code}）
    - 兼容旧版 tenant_id 请求体字段
    """
    owner_type, owner_id = _parse_context_header(x_context, x_user_id, body.tenant_id)
    logger.info(f"[CreateAgent] owner_type={owner_type}, owner_id={owner_id}")

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO agent_config
                (tenant_id, name, description, system_prompt, model, temperature, max_tokens, tools_enabled, knowledge_base_ids, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    owner_id, body.name, body.description, body.system_prompt,
                    body.model, body.temperature, body.max_tokens, body.tools_enabled,
                    body.knowledge_base_ids, body.status
                )
            )
            conn.commit()
            agent_id = cursor.lastrowid

            cursor.execute("SELECT * FROM agent_config WHERE id = %s", (agent_id,))
            row = cursor.fetchone()
            agent = dict(row)
            if agent.get('created_at'):
                agent['created_at'] = str(agent['created_at'])
            if agent.get('temperature'):
                agent['temperature'] = float(agent['temperature'])

            return ApiResponse(data=agent)
    finally:
        conn.close()


@router.put("/agents/{agent_id}", response_model=ApiResponse)
async def update_agent(agent_id: int, body: AgentUpdate):
    """更新 Agent"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            updates = []
            values = []

            if body.name is not None:
                updates.append("name = %s")
                values.append(body.name)
            if body.description is not None:
                updates.append("description = %s")
                values.append(body.description)
            if body.system_prompt is not None:
                updates.append("system_prompt = %s")
                values.append(body.system_prompt)
            if body.model is not None:
                updates.append("model = %s")
                values.append(body.model)
            if body.temperature is not None:
                updates.append("temperature = %s")
                values.append(body.temperature)
            if body.max_tokens is not None:
                updates.append("max_tokens = %s")
                values.append(body.max_tokens)
            if body.tools_enabled is not None:
                updates.append("tools_enabled = %s")
                values.append(body.tools_enabled)
            if body.knowledge_base_ids is not None:
                updates.append("knowledge_base_ids = %s")
                values.append(body.knowledge_base_ids)
            if body.status is not None:
                updates.append("status = %s")
                values.append(body.status)

            if not updates:
                raise HTTPException(status_code=400, detail="没有要更新的字段")

            values.append(agent_id)
            cursor.execute(
                f"UPDATE agent_config SET {', '.join(updates)} WHERE id = %s",
                values
            )
            conn.commit()

            cursor.execute("SELECT * FROM agent_config WHERE id = %s", (agent_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Agent 不存在")

            agent = dict(row)
            if agent.get('created_at'):
                agent['created_at'] = str(agent['created_at'])
            if agent.get('updated_at'):
                agent['updated_at'] = str(agent['updated_at'])
            if agent.get('temperature'):
                agent['temperature'] = float(agent['temperature'])

            return ApiResponse(data=agent)
    finally:
        conn.close()


@router.delete("/agents/{agent_id}", response_model=ApiResponse)
async def delete_agent(agent_id: int):
    """删除 Agent"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM agent_config WHERE id = %s", (agent_id,))
            conn.commit()
            return ApiResponse(data={"deleted": agent_id})
    finally:
        conn.close()
