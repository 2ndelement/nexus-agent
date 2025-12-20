"""
tool-registry 工具注册中心数据模型。

工具定义格式参考 OpenAI function calling schema：
{
    "name": "calculator",
    "description": "执行数学表达式计算",
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "数学表达式，例如 '2+3*4'"}
        },
        "required": ["expression"]
    }
}
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────────────
# 枚举
# ──────────────────────────────────────────────────────────────────────────────

class ToolScope(str, Enum):
    """工具可见范围"""
    BUILTIN = "BUILTIN"   # 内置全局工具，所有租户可用
    TENANT = "TENANT"     # 租户自定义工具，仅本租户可用


class ToolStatus(int, Enum):
    """工具状态"""
    DISABLED = 0
    ENABLED = 1


# ──────────────────────────────────────────────────────────────────────────────
# OpenAI Function Calling Schema
# ──────────────────────────────────────────────────────────────────────────────

class ParameterSchema(BaseModel):
    """工具参数的 JSON Schema 定义"""
    type: str = "object"
    properties: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)


class ToolDefinition(BaseModel):
    """
    工具定义，遵循 OpenAI function calling 格式。

    示例：
    {
        "name": "calculator",
        "description": "执行数学表达式计算",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "数学表达式"}
            },
            "required": ["expression"]
        }
    }
    """
    name: str = Field(..., min_length=1, max_length=100, description="工具名称（唯一标识）")
    description: str = Field(..., min_length=1, max_length=500, description="工具描述")
    parameters: ParameterSchema = Field(default_factory=ParameterSchema, description="参数 JSON Schema")


# ──────────────────────────────────────────────────────────────────────────────
# 数据库模型（ORM）
# ──────────────────────────────────────────────────────────────────────────────

class ToolRecord(BaseModel):
    """工具元数据记录（数据库行对应的 Pydantic 模型）"""
    id: int
    tenant_id: Optional[int]  # None 表示内置全局工具
    name: str
    description: str
    parameters_schema: str    # JSON 字符串
    scope: ToolScope
    status: ToolStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────────────────────────────────────
# 请求/响应模型
# ──────────────────────────────────────────────────────────────────────────────

class RegisterToolRequest(BaseModel):
    """注册（或更新）工具请求"""
    tool: ToolDefinition
    scope: ToolScope = ToolScope.TENANT


class ToolResponse(BaseModel):
    """工具元数据响应"""
    id: int
    tenant_id: Optional[int]
    name: str
    description: str
    parameters: ParameterSchema
    scope: ToolScope
    status: ToolStatus
    created_at: datetime
    updated_at: datetime


class ExecuteToolRequest(BaseModel):
    """工具执行请求"""
    name: str = Field(..., description="工具名称")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="工具入参，对应 parameters schema")
    tenant_id: Optional[int] = Field(None, description="租户ID，用于多租户工具隔离")


class ExecuteToolResponse(BaseModel):
    """工具执行响应"""
    tool_name: str
    result: Any
    success: bool
    error: Optional[str] = None


class ApiResponse(BaseModel):
    """统一 API 响应格式"""
    code: int = 200
    msg: str = "success"
    data: Any = None

    @classmethod
    def success(cls, data: Any = None) -> "ApiResponse":
        return cls(code=200, msg="success", data=data)

    @classmethod
    def fail(cls, code: int, msg: str) -> "ApiResponse":
        return cls(code=code, msg=msg, data=None)
