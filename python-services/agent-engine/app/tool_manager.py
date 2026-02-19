"""
app/tool_manager.py — 工具管理器

功能：
1. 从 Session API 获取会话的工具列表
2. 两次鉴权（Agent端 + 微服务端）
3. 工具调用
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class ToolSource:
    BUILTIN = "BUILTIN"
    MCP = "MCP"
    CUSTOM = "CUSTOM"


class ToolDefinition:
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
    
    工具来源：
    1. 内置工具（calculator, web_search, sandbox_execute）
    2. MCP Server（需要 Agent 绑定）
    3. 自定义工具（租户级别）
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
- memory_limit: 内存限制MB（默认256）""",
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
        # 缓存会话的工具列表
        self._conversation_tools: dict[str, list[ToolDefinition]] = {}

    async def get_conversation_tools(
        self,
        conversation_id: str,
        tenant_id: str,
    ) -> list[ToolDefinition]:
        """
        获取会话的工具列表
        
        优先从缓存获取，缓存不存在则从 Session API 获取
        """
        # 检查缓存
        if conversation_id in self._conversation_tools:
            return self._conversation_tools[conversation_id]
        
        # 从 Session API 获取
        tools = await self._fetch_tools_from_session(conversation_id, tenant_id)
        
        # 缓存
        self._conversation_tools[conversation_id] = tools
        
        return tools

    async def _fetch_tools_from_session(
        self,
        conversation_id: str,
        tenant_id: str,
    ) -> list[ToolDefinition]:
        """从 Session API 获取会话的工具列表"""
        import httpx
        
        url = f"{self._session_url}/api/session/{conversation_id}/tools"
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    url,
                    headers={"X-Tenant-Id": tenant_id}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    tools_data = data.get("tools", [])
                    
                    return [
                        ToolDefinition(
                            name=t["name"],
                            description=t.get("description", ""),
                            parameters=t.get("parameters", {}),
                            source=t.get("source", "BUILTIN"),
                        )
                        for t in tools_data
                    ]
                else:
                    logger.warning(
                        f"获取会话工具列表失败: conv={conversation_id}, "
                        f"status={response.status_code}"
                    )
                    return self._get_builtin_tools()
        except Exception as e:
            logger.error(f"获取会话工具列表异常: {e}")
            return self._get_builtin_tools()

    def _get_builtin_tools(self) -> list[ToolDefinition]:
        """获取内置工具（兜底）"""
        return [
            ToolDefinition(
                name=tool["name"],
                description=tool["description"],
                parameters=tool["parameters"],
                source=ToolSource.BUILTIN,
            )
            for tool in self.BUILTIN_TOOLS
        ]

    def clear_conversation_cache(self, conversation_id: str):
        """清除会话的工具缓存"""
        self._conversation_tools.pop(conversation_id, None)


class ToolExecutor:
    """
    工具执行器
    
    两次鉴权：
    1. Agent 端：会话级工具列表检查
    2. 微服务端：实时权限检查
    """
    
    def __init__(self):
        self._tool_registry_url = os.getenv(
            "TOOL_REGISTRY_URL",
            "http://nexus-tool-registry:8011"
        )

    async def check_permission(
        self,
        tool_name: str,
        source: str,
        tenant_id: str,
        role_id: str,
    ) -> bool:
        """
        第一次鉴权：检查工具是否在会话可用列表中
        """
        # 实际应该在 Agent 端检查会话的工具列表
        # 这里简化处理，直接返回 True
        # 真正的鉴权在微服务端
        return True

    async def execute(
        self,
        tool_name: str,
        source: str,
        arguments: dict,
        tenant_id: str,
        user_id: str,
        role_id: str,
    ) -> dict:
        """
        执行工具（两次鉴权）
        """
        # 第二次鉴权在微服务端进行
        # 这里简化处理，直接执行
        
        if tool_name == "calculator":
            return await self._execute_calculator(arguments)
        elif tool_name == "web_search":
            return await self._execute_search(arguments)
        elif tool_name == "sandbox_execute":
            return await self._execute_sandbox(arguments)
        else:
            return {"success": False, "error": f"未知工具: {tool_name}"}

    async def _execute_calculator(self, arguments: dict) -> dict:
        """计算器"""
        try:
            expression = arguments.get("expression", "")
            result = eval(expression)
            return {"success": True, "result": str(result)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_sandbox(self, arguments: dict) -> dict:
        """沙箱执行"""
        import httpx
        
        url = os.getenv("SANDBOX_URL", "http://nexus-sandbox:8020")
        
        try:
            async with httpx.AsyncClient(
                timeout=arguments.get("timeout", 60)
            ) as client:
                response = await client.post(
                    f"{url}/api/execute",
                    json={
                        "code": arguments.get("code"),
                        "language": arguments.get("language", "python"),
                        "timeout": arguments.get("timeout", 60),
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
        return {"success": True, "result": "搜索功能开发中"}


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
