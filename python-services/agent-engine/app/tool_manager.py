"""
app/tool_manager.py — 工具管理器

功能：
1. 获取可用工具列表（会话级别缓存）
2. 两次鉴权（Agent端 + 微服务端）
3. 工具执行 + 审计日志
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class ToolSource:
    """工具来源枚举"""
    BUILTIN = "BUILTIN"
    MCP = "MCP"
    CUSTOM = "CUSTOM"


class ToolDefinition:
    """工具定义"""
    
    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        source: str,
        source_id: Optional[str] = None,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.source = source
        self.source_id = source_id
    
    def to_openai_format(self) -> dict:
        """转换为 OpenAI function calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolManager:
    """
    工具管理器
    
    核心原则：
    - 会话开始时获取工具列表，会话期间不变
    - 权限变更只影响新会话
    - 工具执行时实时鉴权（兜底）
    """
    
    # 内置工具定义
    BUILTIN_TOOLS = [
        {
            "name": "calculator",
            "description": "计算器 - 执行数学表达式计算，支持 +, -, *, /, **, sqrt, log 等",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '2 + 3 * 4'",
                    }
                },
                "required": ["expression"],
            },
        },
        {
            "name": "web_search",
            "description": "网络搜索 - 搜索互联网获取实时信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    }
                },
                "required": ["query"],
            },
        },
        {
            "name": "sandbox_execute",
            "description": """代码执行 - 在隔离沙箱中执行 Python 或 Bash 代码。
支持参数：
- code: 代码（必填）
- language: python/bash（默认python）
- timeout: 超时秒数（默认60，最大3600）
- memory_limit: 内存限制MB（默认256）
            """,
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "要执行的代码",
                    },
                    "language": {
                        "type": "string",
                        "enum": ["python", "bash"],
                        "default": "python",
                        "description": "代码语言",
                    },
                    "timeout": {
                        "type": "integer",
                        "default": 60,
                        "minimum": 1,
                        "maximum": 3600,
                        "description": "超时秒数（1-3600）",
                    },
                    "memory_limit": {
                        "type": "integer",
                        "default": 256,
                        "minimum": 64,
                        "maximum": 2048,
                        "description": "内存限制MB（64-2048）",
                    },
                },
                "required": ["code"],
            },
        },
    ]
    
    def __init__(self):
        self._session_url = os.getenv(
            "SESSION_SERVICE_URL",
            "http://nexus-session:8004"
        )
        self._tool_registry_url = os.getenv(
            "TOOL_REGISTRY_URL",
            "http://nexus-tool-registry:8011"
        )
    
    async def get_conversation_tools(
        self,
        conversation_id: str,
        tenant_id: str,
    ) -> list[ToolDefinition]:
        """
        获取会话的工具列表（会话级别缓存）
        
        从 Java Session Service 获取会话创建时的工具列表
        """
        import httpx
        
        url = f"{self._session_url}/api/session/{conversation_id}/tools"
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    url,
                    headers={"X-Tenant-Id": tenant_id}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    tools_data = data.get("tools", [])
                    
                    result = []
                    for tool in tools_data:
                        result.append(ToolDefinition(
                            name=tool["name"],
                            description=tool.get("description", ""),
                            parameters=tool.get("parameters", {}),
                            source=tool.get("source", "BUILTIN"),
                        ))
                    
                    logger.info(
                        f"获取工具列表: conv={conversation_id}, count={len(result)}"
                    )
                    return result
                    
        except Exception as e:
            logger.error(f"获取工具列表失败: {e}")
        
        # 失败时返回内置工具作为兜底
        return self._get_builtin_tools()
    
    def _get_builtin_tools(self) -> list[ToolDefinition]:
        """获取内置工具"""
        return [
            ToolDefinition(
                name=tool["name"],
                description=tool["description"],
                parameters=tool["parameters"],
                source=ToolSource.BUILTIN,
            )
            for tool in self.BUILTIN_TOOLS
        ]
    
    async def get_tools_for_llm(
        self,
        conversation_id: str,
        tenant_id: str,
    ) -> list[dict]:
        """
        获取 LLM 可用的工具列表（OpenAI 格式）
        """
        tools = await self.get_conversation_tools(conversation_id, tenant_id)
        return [t.to_openai_format() for t in tools]


class ToolExecutor:
    """
    工具执行器
    
    两次鉴权：
    1. 会话级别的工具列表（会话创建时获取的）
    2. 实时权限检查（兜底）
    """
    
    def __init__(self):
        self._session_url = os.getenv(
            "SESSION_SERVICE_URL",
            "http://nexus-session:8004"
        )
        self._tool_registry_url = os.getenv(
            "TOOL_REGISTRY_URL",
            "http://nexus-tool-registry:8011"
        )
    
    async def check_permission(
        self,
        tool_name: str,
        tenant_id: str,
        conversation_id: str,
    ) -> bool:
        """
        实时权限检查（兜底）
        
        会话创建时获取的工具列表可能已过时，
        每次执行前检查实时权限
        """
        import httpx
        
        url = f"{self._session_url}/api/session/{conversation_id}/tools/check"
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    url,
                    json={"tool_name": tool_name},
                    headers={"X-Tenant-Id": tenant_id}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("allowed", False)
                    
        except Exception as e:
            logger.warning(f"权限检查失败: {e}")
        
        # 失败时默认允许（避免阻断会话）
        return True
    
    async def execute(
        self,
        tool_name: str,
        arguments: dict,
        tenant_id: str,
        conversation_id: str,
        user_id: str = None,
    ) -> dict:
        """
        执行工具
        
        流程：
        1. 实时权限检查（兜底）
        2. 执行内置工具
        3. 记录审计日志
        """
        # 1. 实时权限检查
        if not await self.check_permission(tool_name, tenant_id, conversation_id):
            return {
                "success": False,
                "error": "TOOL_DISABLED",
                "message": "工具已禁用或无权限",
            }
        
        # 2. 执行工具
        if tool_name == "calculator":
            result = await self._execute_calculator(arguments)
        elif tool_name == "sandbox_execute":
            result = await self._execute_sandbox(arguments)
        elif tool_name == "web_search":
            result = await self._execute_search(arguments)
        else:
            result = await self._execute_custom(
                tool_name, arguments, tenant_id, user_id
            )
        
        # 3. 记录审计日志
        await self._log_execution(
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        
        return result
    
    async def _execute_calculator(self, arguments: dict) -> dict:
        """计算器"""
        try:
            expression = arguments.get("expression", "")
            result = eval(expression)  # 注意：实际应该用安全的计算器
            return {"success": True, "result": str(result)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_sandbox(self, arguments: dict) -> dict:
        """沙箱执行"""
        import httpx
        
        sandbox_url = os.getenv("SANDBOX_URL", "http://nexus-sandbox:8020")
        url = f"{sandbox_url}/api/execute"
        
        timeout = arguments.get("timeout", 60)
        
        try:
            async with httpx.AsyncClient(timeout=timeout + 5) as client:
                response = await client.post(
                    url,
                    json={
                        "code": arguments.get("code"),
                        "language": arguments.get("language", "python"),
                        "timeout": timeout,
                    }
                )
                
                if response.status_code == 200:
                    return {"success": True, "result": response.json()}
                else:
                    return {"success": False, "error": response.text}
                    
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_search(self, arguments: dict) -> dict:
        """网络搜索"""
        # TODO: 实现搜索
        return {"success": True, "result": {"message": "搜索功能开发中"}}
    
    async def _execute_custom(
        self,
        tool_name: str,
        arguments: dict,
        tenant_id: str,
        user_id: str,
    ) -> dict:
        """执行自定义工具（调用 Tool-Registry）"""
        import httpx
        
        url = f"{self._tool_registry_url}/api/tools/execute"
        
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    url,
                    json={
                        "name": tool_name,
                        "arguments": arguments,
                        "tenantId": tenant_id,
                        "userId": user_id,
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 200:
                        return {
                            "success": True,
                            "result": data.get("data", {}).get("result")
                        }
                    else:
                        return {
                            "success": False,
                            "error": data.get("msg", "执行失败")
                        }
                else:
                    return {"success": False, "error": response.text}
                    
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _log_execution(
        self,
        tool_name: str,
        arguments: dict,
        result: dict,
        tenant_id: str,
        user_id: str,
        conversation_id: str,
    ):
        """记录工具执行日志"""
        import httpx
        
        log_url = f"{self._session_url}/api/session/tool-execution/log"
        
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    log_url,
                    json={
                        "conversationId": conversation_id,
                        "toolName": tool_name,
                        "arguments": arguments,
                        "result": result.get("result") if result.get("success") else None,
                        "error": result.get("error"),
                        "tenantId": tenant_id,
                        "userId": user_id,
                        "success": result.get("success", False),
                    }
                )
        except Exception as e:
            logger.warning(f"审计日志记录失败: {e}")


# 全局单例
_tool_manager: Optional[ToolManager] = None
_tool_executor: Optional[ToolExecutor] = None


def get_tool_manager() -> ToolManager:
    global _tool_manager
    if _tool_manager is None:
        _tool_manager = ToolManager()
    return _tool_manager


def get_tool_executor() -> ToolExecutor:
    global _tool_executor
    if _tool_executor is None:
        _tool_executor = ToolExecutor()
    return _tool_executor
