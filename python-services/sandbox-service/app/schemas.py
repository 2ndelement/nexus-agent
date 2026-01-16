"""
app/schemas.py — API Schema
"""
from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    """代码执行请求"""
    code: str = Field(..., description="要执行的代码")
    language: str = Field(default="python", description="语言: python | bash")
    timeout: int = Field(default=30, ge=1, le=120, description="超时秒数")


class ExecuteResponse(BaseModel):
    """代码执行响应"""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    error: str | None = None
