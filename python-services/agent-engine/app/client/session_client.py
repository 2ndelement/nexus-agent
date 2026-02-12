"""
app/client/session_client.py — Java Session Service 客户端

功能：
- 调用 Java Session API 保存聊天记录
- 获取对话历史
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class MessageRole:
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class SessionClient:
    """
    Java Session Service HTTP 客户端
    """

    def __init__(self):
        self._base_url: Optional[str] = None
        self._initialized = False

    def initialize(self):
        """初始化客户端"""
        # 从环境变量获取 Session Service 地址
        # 或通过 Nacos 服务发现
        self._base_url = os.getenv(
            "SESSION_SERVICE_URL",
            os.getenv("NEXUS_SESSION_URL", "http://nexus-session:8004")
        )
        self._initialized = True
        logger.info(f"[SessionClient] 初始化完成: {self._base_url}")

    async def add_message(
        self,
        conversation_id: str,
        tenant_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> bool:
        """
        添加消息
        
        Args:
            conversation_id: 会话ID
            tenant_id: 租户ID
            role: 角色 (user/assistant/tool)
            content: 消息内容
            metadata: 额外元数据
        
        Returns:
            是否成功
        """
        if not self._initialized:
            self.initialize()

        try:
            import httpx
            
            url = f"{self._base_url}/api/session/{conversation_id}/message"
            payload = {
                "tenantId": tenant_id,
                "role": role,
                "content": content,
                "metadata": metadata,
            }
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload)
                
                if response.status_code in (200, 201):
                    logger.debug(f"[SessionClient] 消息保存成功: conv={conversation_id}, role={role}")
                    return True
                else:
                    logger.error(f"[SessionClient] 消息保存失败: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"[SessionClient] 添加消息异常: {e}")
            return False

    async def add_user_message(
        self,
        conversation_id: str,
        tenant_id: str,
        content: str,
    ) -> bool:
        """添加用户消息"""
        return await self.add_message(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            role=MessageRole.USER,
            content=content,
        )

    async def add_assistant_message(
        self,
        conversation_id: str,
        tenant_id: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> bool:
        """添加 AI 助手消息"""
        return await self.add_message(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            role=MessageRole.ASSISTANT,
            content=content,
            metadata=metadata,
        )

    async def add_tool_message(
        self,
        conversation_id: str,
        tenant_id: str,
        content: str,
        tool_name: str,
        tool_args: dict,
        tool_result: str,
    ) -> bool:
        """添加工具消息"""
        metadata = {
            "type": "tool_call",
            "tool_name": tool_name,
            "tool_args": tool_args,
            "result": tool_result,
        }
        return await self.add_message(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            role=MessageRole.TOOL,
            content=content,
            metadata=metadata,
        )

    async def get_messages(
        self,
        conversation_id: str,
        tenant_id: str,
    ) -> list[dict]:
        """
        获取对话历史
        
        Args:
            conversation_id: 会话ID
            tenant_id: 租户ID
        
        Returns:
            消息列表
        """
        if not self._initialized:
            self.initialize()

        try:
            import httpx
            
            url = f"{self._base_url}/api/session/{conversation_id}/messages"
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    url,
                    params={"tenantId": tenant_id}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("messages", [])
                else:
                    logger.error(f"[SessionClient] 获取消息失败: {response.status_code}")
                    return []
                    
        except Exception as e:
            logger.error(f"[SessionClient] 获取消息异常: {e}")
            return []


# 全局单例
_session_client: Optional[SessionClient] = None


def get_session_client() -> SessionClient:
    """获取 Session 客户端"""
    global _session_client
    if _session_client is None:
        _session_client = SessionClient()
        _session_client.initialize()
    return _session_client
