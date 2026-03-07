"""
app/schemas.py — API Schema

V5 更新：
- 新增 owner_type, owner_id, conversation_id 支持会话隔离
- 新增 workspace_files 返回工作区文件列表
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    """代码执行请求"""
    code: str = Field(..., description="要执行的代码")
    language: str = Field(default="python", description="语言: python | bash")
    timeout: int = Field(default=30, ge=1, le=120, description="超时秒数")

    # V5 新增：会话上下文（用于工作区隔离）
    owner_type: str = Field(default="PERSONAL", description="所有者类型: PERSONAL | ORGANIZATION")
    owner_id: str = Field(default="", description="所有者 ID (user_id 或 org_code)")
    conversation_id: str = Field(default="", description="会话 ID")


class WorkspaceFileInfo(BaseModel):
    """工作区文件详细信息（用于执行结果返回）"""
    name: str
    size: int
    mime_type: str


class ExecuteResponse(BaseModel):
    """代码执行响应"""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    error: str | None = None

    # V5 新增
    workspace_files: List[WorkspaceFileInfo] = Field(default_factory=list, description="工作区新生成的文件列表")
    session_id: str | None = Field(default=None, description="会话容器 ID (用于复用)")


class WorkspaceFile(BaseModel):
    """工作区文件信息"""
    name: str
    size: int
    modified_at: str
    is_dir: bool = False


class WorkspaceListResponse(BaseModel):
    """工作区文件列表响应"""
    files: List[WorkspaceFile]
    total_size: int
    workspace_path: str
