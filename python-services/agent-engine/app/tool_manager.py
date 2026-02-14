"""
app/tool_manager.py — 工具管理器

功能：
1. 获取可用工具列表（内置 + MCP + 自定义）
2. 根据用户权限过滤
3. 两次鉴权（Agent端 + 微服务端）
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
    
    工具来源：
    1. 内置工具（calculator, web_search, sandbox_execute）
    2. MCP Server 工具（需要 Agent 绑定）
    3. Tool-Registry 自定义工具（租户级别）
    """
    
    # 内置工具定义
    BUILTIN_TOOLS = [
        {
            "name": "calculator",
            "description": "执行数学表达式计算。支持 +, -, *, /, **, sqrt, log 等",
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
            "description": "搜索互联网获取实时信息",
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
            "description": "在隔离沙箱中执行 Python 或 Bash 代码。

参数：
- code: 代码（必填）
- language: python/bash（默认python）
- timeout: 超时秒数（默认60，最大3600）
- memory_limit: 内存限制MB（默认256）",
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
        self._http_client = None
        self._mcp_clients: dict[str, MCPClient] = {}
        self._tool_registry_url = os.getenv(
            "TOOL_REGISTRY_URL",
            "http://nexus-tool-registry:8011"
        )
        self._mcp_manager_url = os.getenv(
            "MCP_MANAGER_URL",
            "http://nexus-mcp-manager:8009"
        )
    
    async def get_available_tools(
        self,
        agent_id: str,
        tenant_id: str,
        user_id: str,
        role_id: str,
    ) -> list[ToolDefinition]:
        """
        获取用户可用的工具列表
        
        流程：
        1. 获取内置工具
        2. 获取 Agent 绑定的 MCP Server 工具
        3. 获取租户自定义工具
        4. 根据角色权限过滤
        """
        tools = []
        
        # 1. 内置工具（全部可见）
        for tool_def in self.BUILTIN_TOOLS:
            tools.append(ToolDefinition(
                name=tool_def["name"],
                description=tool_def["description"],
                parameters=tool_def["parameters"],
                source=ToolSource.BUILTIN,
            ))
        
        # 2. MCP Server 工具（需要 Agent 绑定）
        try:
            mcp_tools = await self._get_mcp_tools(agent_id, tenant_id)
            tools.extend(mcp_tools)
        except Exception as e:
            logger.warning(f"获取 MCP 工具失败: {e}")
        
        # 3. 租户自定义工具
        try:
            custom_tools = await self._get_custom_tools(tenant_id)
            tools.extend(custom_tools)
        except Exception as e:
            logger.warning(f"获取自定义工具失败: {e}")
        
        # 4. 根据角色权限过滤
        allowed_tools = await self._filter_by_permission(tools, tenant_id, role_id)
        
        return allowed_tools
    
    async def _get_mcp_tools(self, agent_id: str, tenant_id: str) -> list[ToolDefinition]:
        """获取 MCP Server 工具"""
        import httpx
        
        # 获取 Agent 绑定的 MCP Servers
        url = f"{self._mcp_manager_url}/api/agent/{agent_id}/mcp"
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                url,
                headers={"X-Tenant-Id": tenant_id}
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            servers = data.get("servers", [])
        
        tools = []
        for server in servers:
            # TODO: 从 MCP Server 获取工具列表
            # 目前简化处理，假设 MCP Server 提供了工具
            pass
        
        return tools
    
    async def _get_custom_tools(self, tenant_id: str) -> list[ToolDefinition]:
        """获取租户自定义工具"""
        import httpx
        
        url = f"{self._tool_registry_url}/api/tools"
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                url,
                headers={"X-Tenant-Id": tenant_id}
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            tools_data = data.get("data", [])
        
        tools = []
        for tool in tools_data:
            tools.append(ToolDefinition(
                name=tool["name"],
                description=tool["description"],
                parameters=tool.get("parameters", {}),
                source=ToolSource.CUSTOM,
                source_id=str(tool.get("id")),
            ))
        
        return tools
    
    async def _filter_by_permission(
        self,
        tools: list[ToolDefinition],
        tenant_id: str,
        role_id: str,
    ) -> list[ToolDefinition]:
        """根据角色权限过滤工具"""
        import httpx
        
        # 从权限服务获取角色可用的工具
        # TODO: 调用 Java 权限服务
        # 目前返回所有工具
        
        return tools


class ToolExecutor:
    """
    工具执行器
    执行两次鉴权
    """
    
    def __init__(self):
        self._tool_registry_url = os.getenv(
            "TOOL_REGISTRY_URL",
            "http://nexus-tool-registry:8011"
        )
    
    async def check_permission(
        self,
        tool_name: str,
        tool_source: str,
        tenant_id: str,
        role_id: str,
    ) -> bool:
        """第一次鉴权：Agent 端快速检查"""
        # TODO: 调用 Java 权限服务
        return True
    
    async def execute(
        self,
        tool_name: str,
        tool_source: str,
        arguments: dict,
        tenant_id: str,
        user_id: str,
        role_id: str,
    ) -> dict:
        """
        执行工具（两次鉴权）
        
        第一次鉴权：Agent 端
        第二次鉴权：微服务端
        """
        # 第一次鉴权
        if not await self.check_permission(tool_name, tool_source, tenant_id, role_id):
            return {
                "success": False,
                "error": "无权限使用该工具"
            }
        
        # 调用微服务端执行（第二次鉴权）
        if tool_source == ToolSource.BUILTIN:
            return await self._execute_builtin(tool_name, arguments)
        elif tool_source == ToolSource.MCP:
            return await self._execute_mcp(tool_name, arguments, tenant_id)
        elif tool_source == ToolSource.CUSTOM:
            return await self._execute_custom(tool_name, arguments, tenant_id, user_id)
        
        return {"success": False, "error": "未知工具来源"}
    
    async def _execute_builtin(self, tool_name: str, arguments: dict) -> dict:
        """执行内置工具"""
        if tool_name == "calculator":
            return await self._execute_calculator(arguments)
        elif tool_name == "sandbox_execute":
            return await self._execute_sandbox(arguments)
        elif tool_name == "web_search":
            return await self._execute_search(arguments)
        
        return {"success": False, "error": f"未知内置工具: {tool_name}"}
    
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
        
        url = f"{os.getenv('SANDBOX_URL', 'http://nexus-sandbox:8020')}/api/execute"
        
        try:
            async with httpx.AsyncClient(timeout=arguments.get("timeout", 60)) as client:
                response = await client.post(url, json={
                    "code": arguments.get("code"),
                    "language": arguments.get("language", "python"),
                    "timeout": arguments.get("timeout", 60),
                })
                
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
    
    async def _execute_mcp(self, tool_name: str, arguments: dict, tenant_id: str) -> dict:
        """执行 MCP 工具"""
        # TODO: 调用 MCP Server
        return {"success": False, "error": "MCP 工具执行开发中"}
    
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
                        return {"success": False, "error": data.get("msg", "执行失败")}
                else:
                    return {"success": False, "error": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}


class MCPClient:
    """MCP 客户端"""
    
    def __init__(self, server_id: str, config: dict):
        self.server_id = server_id
        self.config = config
        self._connected = False
    
    async def connect(self):
        """连接 MCP Server"""
        transport = self.config.get("transport", "sse")
        url = self.config.get("url")
        
        if transport == "sse":
            # SSE 连接
            pass
        elif transport == "streamable_http":
            # Streamable HTTP 连接
            pass
        
        self._connected = True
    
    async def list_tools(self) -> list[dict]:
        """获取工具列表"""
        # TODO: 实现
        return []
    
    async def call_tool(self, name: str, arguments: dict) -> dict:
        """调用工具"""
        # TODO: 实现
        return {"success": False, "error": "MCP 工具调用开发中"}
    
    async def close(self):
        """关闭连接"""
        self._connected = False


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
