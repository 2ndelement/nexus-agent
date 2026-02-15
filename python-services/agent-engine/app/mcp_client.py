"""
app/mcp_client.py — MCP 客户端

支持 SSE 和 Streamable HTTP 两种传输方式
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    """MCP 客户端错误"""
    pass


class MCPClient:
    """
    MCP 客户端
    
    支持两种传输方式：
    - SSE: Server-Sent Events
    - Streamable HTTP: 轮询获取进度
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.transport = config.get("transport", "sse")
        self.url = config["url"]
        self.headers = config.get("headers", {})
        self.timeout = config.get("timeout", 30)
        self._connected = False
    
    async def connect(self) -> bool:
        """连接 MCP Server"""
        try:
            if self.transport == "sse":
                return await self._connect_sse()
            elif self.transport == "streamable_http":
                return await self._connect_streamable()
            else:
                raise MCPClientError(f"Unknown transport: {self.transport}")
        except Exception as e:
            logger.error(f"MCP 连接失败: {e}")
            return False
    
    async def _connect_sse(self) -> bool:
        """SSE 连接"""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # 发送 initializ 请求
                response = await client.post(
                    self.url,
                    json={"jsonrpc": "2.0", "method": "initialize", "params": {}},
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    self._connected = True
                    logger.info(f"MCP SSE 连接成功: {self.url}")
                    return True
                else:
                    logger.error(f"MCP SSE 连接失败: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"MCP SSE 连接异常: {e}")
            return False
    
    async def _connect_streamable(self) -> bool:
        """Streamable HTTP 连接"""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.url,
                    json={"jsonrpc": "2.0", "method": "initialize", "params": {}},
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    self._connected = True
                    logger.info(f"MCP Streamable HTTP 连接成功: {self.url}")
                    return True
                else:
                    logger.error(f"MCP 连接失败: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"MCP Streamable HTTP 连接异常: {e}")
            return False
    
    async def list_tools(self) -> list[dict]:
        """获取工具列表"""
        if not self._connected:
            if not await self.connect():
                return []
        
        if self.transport == "sse":
            return await self._list_tools_sse()
        else:
            return await self._list_tools_streamable()
    
    async def _list_tools_sse(self) -> list[dict]:
        """SSE 获取工具列表"""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.url,
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/list",
                        "id": "1"
                    },
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("result", {}).get("tools", [])
                return []
        except Exception as e:
            logger.error(f"MCP list_tools 失败: {e}")
            return []
    
    async def _list_tools_streamable(self) -> list[dict]:
        """Streamable HTTP 获取工具列表"""
        # 类似 SSE 实现
        return await self._list_tools_sse()
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict
    ) -> dict:
        """调用工具"""
        if not self._connected:
            return {"error": "MCP 未连接"}
        
        if self.transport == "sse":
            return await self._call_tool_sse(tool_name, arguments)
        else:
            return await self._call_tool_streamable(tool_name, arguments)
    
    async def _call_tool_sse(
        self,
        tool_name: str,
        arguments: dict
    ) -> dict:
        """SSE 调用工具"""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.url,
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {
                            "name": tool_name,
                            "arguments": arguments
                        },
                        "id": "1"
                    },
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result = data.get("result", {})
                    return {
                        "success": True,
                        "result": result
                    }
                else:
                    return {
                        "success": False,
                        "error": response.text
                    }
        except Exception as e:
            logger.error(f"MCP call_tool 失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _call_tool_streamable(
        self,
        tool_name: str,
        arguments: dict
    ) -> dict:
        """Streamable HTTP 调用工具"""
        # 类似 SSE 实现
        return await self._call_tool_sse(tool_name, arguments)
    
    async def close(self):
        """关闭连接"""
        self._connected = False
        logger.info(f"MCP 连接关闭: {self.url}")


class MCPClientManager:
    """
    MCP 客户端管理器
    管理多个 MCP Server 连接
    """
    
    def __init__(self):
        self._clients: dict[int, MCPClient] = {}  # server_id -> client
    
    async def connect(self, server_id: int, config: dict) -> bool:
        """连接 MCP Server"""
        client = MCPClient(config)
        success = await client.connect()
        if success:
            self._clients[server_id] = client
        logger.info(f"MCP Server 连接成功: id={server_id}")
        return True
        return False
    
    async def disconnect(self, server_id: int):
        """断开连接"""
        if server_id in self._clients:
            await self._clients[server_id].close()
            del self._clients[server_id]
            logger.info(f"MCP Server 断开连接: id={server_id}")
    
    async def list_tools(self, server_id: int) -> list[dict]:
        """获取指定 Server 的工具列表"""
        if server_id not in self._clients:
            return []
        return await self._clients[server_id].list_tools()
    
    async def call_tool(
        self,
        server_id: int,
        tool_name: str,
        arguments: dict
    ) -> dict:
        """调用指定 Server 的工具"""
        if server_id not in self._clients:
            return {"success": False, "error": "Server 未连接"}
        return await self._clients[server_id].call_tool(tool_name, arguments)
    
    def is_connected(self, server_id: int) -> bool:
        """检查是否连接"""
        return server_id in self._clients


# 全局单例
_mcp_manager: Optional[MCPClientManager] = None


def get_mcp_client_manager() -> MCPClientManager:
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPClientManager()
    return _mcp_manager
