"""
memory-service FastAPI 路由
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from services.memory_service import save_memory, retrieve_memories, delete_memory

router = APIRouter(prefix="/memories", tags=["memory"])


# ─── 请求 / 响应 Schema ────────────────────────────────────────────────────────

class SaveMemoryRequest(BaseModel):
    tenant_id: int = Field(..., description="租户ID，不可为空")
    content: str = Field(..., min_length=1, description="记忆内容")
    user_id: Optional[int] = Field(None, description="用户ID")
    agent_id: Optional[int] = Field(None, description="AgentID")
    source: Optional[str] = Field(None, max_length=100, description="来源标识")
    importance: float = Field(default=1.0, ge=0.0, le=10.0, description="重要性 0-10")


class MemoryResponse(BaseModel):
    id: int
    tenant_id: int
    user_id: Optional[int]
    agent_id: Optional[int]
    content: str
    source: Optional[str]
    importance: float
    score: float = 0.0
    created_at: Optional[str]
    updated_at: Optional[str]


class SaveMemoryResponse(BaseModel):
    success: bool
    memory: MemoryResponse


class RetrieveResponse(BaseModel):
    total: int
    memories: list[MemoryResponse]


class DeleteResponse(BaseModel):
    success: bool
    message: str


# ─── 数据库依赖注入 ──────────────────────────────────────────────────────────

async def get_db():
    """从 main.py 注册的 app.state 获取 AsyncSession。"""
    from main import async_session_factory
    async with async_session_factory() as session:
        yield session


# ─── 接口实现 ────────────────────────────────────────────────────────────────

@router.post("", response_model=SaveMemoryResponse, status_code=201)
async def save_memory_api(
    request: SaveMemoryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    保存记忆片段。

    - 自动生成 embedding（sentence-transformers，失败则降级关键词）
    - 多租户隔离：tenant_id 必填
    """
    mem = await save_memory(
        db,
        tenant_id=request.tenant_id,
        content=request.content,
        user_id=request.user_id,
        agent_id=request.agent_id,
        source=request.source,
        importance=request.importance,
    )
    return SaveMemoryResponse(
        success=True,
        memory=MemoryResponse(
            id=mem.id,
            tenant_id=mem.tenant_id,
            user_id=mem.user_id,
            agent_id=mem.agent_id,
            content=mem.content,
            source=mem.source,
            importance=mem.importance or 1.0,
            score=0.0,
            created_at=mem.created_at.isoformat() if mem.created_at else None,
            updated_at=mem.updated_at.isoformat() if mem.updated_at else None,
        ),
    )


@router.get("", response_model=RetrieveResponse)
async def retrieve_memories_api(
    query: str = Query(..., min_length=1, description="检索查询词"),
    tenant_id: int = Query(..., description="租户ID（必填，保证数据隔离）"),
    user_id: Optional[int] = Query(None, description="过滤用户ID"),
    agent_id: Optional[int] = Query(None, description="过滤AgentID"),
    top_k: int = Query(default=10, ge=1, le=100, description="返回条数上限"),
    db: AsyncSession = Depends(get_db),
):
    """
    检索记忆。

    优先使用向量相似度，模型不可用时自动降级为关键词匹配。
    所有查询均严格隔离到指定 tenant_id。
    """
    results = await retrieve_memories(
        db,
        tenant_id=tenant_id,
        query=query,
        user_id=user_id,
        agent_id=agent_id,
        top_k=top_k,
    )
    return RetrieveResponse(
        total=len(results),
        memories=[MemoryResponse(**r) for r in results],
    )


@router.delete("/{memory_id}", response_model=DeleteResponse)
async def delete_memory_api(
    memory_id: int,
    tenant_id: int = Query(..., description="租户ID，只能删除属于该租户的记录"),
    db: AsyncSession = Depends(get_db),
):
    """
    删除记忆。

    只能删除属于指定租户的记录，跨租户删除会返回 404。
    """
    success = await delete_memory(db, memory_id=memory_id, tenant_id=tenant_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"记忆 {memory_id} 不存在或不属于租户 {tenant_id}",
        )
    return DeleteResponse(success=True, message=f"记忆 {memory_id} 已删除")
