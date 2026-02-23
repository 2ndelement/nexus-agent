"""
app/client/session_client.py — Java Session Service 客户端

功能：
- 调用 Java Session API 保存聊天记录
- 获取对话历史
- 通过 Nacos 服务发现调用
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from common.nacos import discover_service

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
    通过 Nacos 服务发现调用 nexus-session
    """

    def __init__(self):
        self._fallback_url: Optional[str] = None
        self._initialized = False

    def initialize(self):
        """初始化客户端"""
        # 降级地址从环境变量获取
        self._fallback_url = os.getenv(
            "SESSION_SERVICE_URL",
            os.getenv("NEXUS_SESSION_URL", "http://127.0.0.1:8004")
        )
        self._initialized = True
        logger.info(f"[SessionClient] 初始化完成，降级地址: {self._fallback_url}")

    def _get_base_url(self) -> str:
        """通过 Nacos 获取 Session Service 地址"""
        url = discover_service("nexus-session", fallback=self._fallback_url)
        return url or self._fallback_url

    async def add_message(
        self,
        conversation_id: str,
        owner_type: str,
        owner_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> bool:
        """
        添加消息

        V5 重构：使用 owner_type + owner_id 替代 tenant_id

        Args:
            conversation_id: 会话ID
            owner_type: 所有者类型 (PERSONAL/ORGANIZATION)
            owner_id: 所有者ID (user_id 或 org_id)
            user_id: 用户ID
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
            import json as json_lib

            # Java Session API: POST /api/session/conversations/{convId}/messages
            url = f"{self._get_base_url()}/api/session/conversations/{conversation_id}/messages"

            # Java expects metadata as JSON string, not dict
            metadata_str = None
            if metadata:
                metadata_str = json_lib.dumps(metadata) if isinstance(metadata, dict) else str(metadata)

            payload = {
                "role": role,
                "content": content,
                "metadata": metadata_str,
            }
            headers = {
                "X-Owner-Type": str(owner_type),
                "X-Owner-Id": str(owner_id),
                "X-User-Id": str(user_id),
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code in (200, 201):
                    # Java 服务可能返回 HTTP 200 但业务码非 200（如会话不存在返回 code=404）
                    try:
                        resp_data = response.json()
                        if resp_data.get("code") == 200 or resp_data.get("success") is True:
                            logger.debug(f"[SessionClient] 消息保存成功: conv={conversation_id}, role={role}")
                            return True
                        else:
                            # 会话不存在，尝试先创建会话
                            if resp_data.get("code") == 404:
                                logger.info(f"[SessionClient] 会话不存在，尝试创建: conv={conversation_id}")
                                created = await self._create_conversation(conversation_id, owner_type, owner_id, user_id)
                                if created:
                                    # 重试添加消息
                                    response2 = await client.post(url, json=payload, headers=headers)
                                    if response2.status_code in (200, 201):
                                        resp_data2 = response2.json()
                                        if resp_data2.get("code") == 200 or resp_data2.get("success") is True:
                                            logger.debug(f"[SessionClient] 消息保存成功（重试）: conv={conversation_id}, role={role}")
                                            return True
                            logger.error(f"[SessionClient] 消息保存失败: {resp_data.get('msg', 'Unknown error')}")
                            return False
                    except Exception as parse_err:
                        logger.debug(f"[SessionClient] 消息保存成功（无法解析响应）: conv={conversation_id}")
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
        owner_type: str,
        owner_id: str,
        user_id: str,
        content: str,
    ) -> bool:
        """添加用户消息"""
        return await self.add_message(
            conversation_id=conversation_id,
            owner_type=owner_type,
            owner_id=owner_id,
            user_id=user_id,
            role=MessageRole.USER,
            content=content,
        )

    async def _create_conversation(
        self,
        conversation_id: str,
        owner_type: str,
        owner_id: str,
        user_id: str,
        title: str = "新对话",
    ) -> bool:
        """
        创建会话（内部方法）

        V5 重构：使用 owner_type + owner_id 替代 tenant_id

        Args:
            conversation_id: 会话ID
            owner_type: 所有者类型 (PERSONAL/ORGANIZATION)
            owner_id: 所有者ID
            user_id: 用户ID
            title: 会话标题

        Returns:
            是否成功
        """
        try:
            import httpx

            # Java Session API: POST /api/session/conversations
            url = f"{self._get_base_url()}/api/session/conversations"
            payload = {
                "conversationId": conversation_id,
                "title": title,
            }
            headers = {
                "X-Owner-Type": str(owner_type),
                "X-Owner-Id": str(owner_id),
                "X-User-Id": str(user_id),
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code in (200, 201):
                    resp_data = response.json()
                    if resp_data.get("code") == 200 or resp_data.get("success") is True:
                        logger.info(f"[SessionClient] 会话创建成功: conv={conversation_id}")
                        return True
                    else:
                        logger.error(f"[SessionClient] 会话创建失败: {resp_data.get('msg', 'Unknown')}")
                        return False
                else:
                    logger.error(f"[SessionClient] 会话创建失败: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"[SessionClient] 创建会话异常: {e}")
            return False

    async def add_assistant_message(
        self,
        conversation_id: str,
        owner_type: str,
        owner_id: str,
        user_id: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> bool:
        """添加 AI 助手消息"""
        return await self.add_message(
            conversation_id=conversation_id,
            owner_type=owner_type,
            owner_id=owner_id,
            user_id=user_id,
            role=MessageRole.ASSISTANT,
            content=content,
            metadata=metadata,
        )

    async def add_tool_message(
        self,
        conversation_id: str,
        owner_type: str,
        owner_id: str,
        user_id: str,
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
            owner_type=owner_type,
            owner_id=owner_id,
            user_id=user_id,
            role=MessageRole.TOOL,
            content=content,
            metadata=metadata,
        )

    async def get_conversation(
        self,
        conversation_id: str,
        owner_type: str,
        owner_id: str,
    ) -> dict | None:
        """获取会话详情。"""
        if not self._initialized:
            self.initialize()

        try:
            import httpx

            url = f"{self._get_base_url()}/api/session/conversations/{conversation_id}"
            headers = {
                "X-Owner-Type": str(owner_type),
                "X-Owner-Id": str(owner_id),
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data") or data
                logger.error(f"[SessionClient] 获取会话详情失败: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"[SessionClient] 获取会话详情异常: {e}")
            return None

    async def update_title(
        self,
        conversation_id: str,
        owner_type: str,
        owner_id: str,
        user_id: str,
        title: str,
    ) -> bool:
        """
        更新会话标题

        V5 重构：使用 owner_type + owner_id 替代 tenant_id

        Args:
            conversation_id: 会话ID
            owner_type: 所有者类型 (PERSONAL/ORGANIZATION)
            owner_id: 所有者ID
            user_id: 用户ID
            title: 新标题

        Returns:
            是否成功
        """
        if not self._initialized:
            self.initialize()

        try:
            import httpx

            url = f"{self._get_base_url()}/api/session/conversations/{conversation_id}/title"
            headers = {
                "X-Owner-Type": str(owner_type),
                "X-Owner-Id": str(owner_id),
                "X-User-Id": str(user_id),
                "Content-Type": "application/json",
            }
            payload = {"title": title}

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.put(url, json=payload, headers=headers)

                if response.status_code in (200, 201):
                    logger.info(f"[SessionClient] 标题更新成功: conv={conversation_id}, title={title}")
                    return True
                else:
                    logger.error(f"[SessionClient] 标题更新失败: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"[SessionClient] 更新标题异常: {e}")
            return False

    async def get_messages(
        self,
        conversation_id: str,
        owner_type: str,
        owner_id: str,
    ) -> list[dict]:
        """
        获取对话历史

        V5 重构：使用 owner_type + owner_id 替代 tenant_id

        Args:
            conversation_id: 会话ID
            owner_type: 所有者类型 (PERSONAL/ORGANIZATION)
            owner_id: 所有者ID

        Returns:
            消息列表
        """
        if not self._initialized:
            self.initialize()

        try:
            import httpx

            # Java Session API: GET /api/session/conversations/{convId}/messages
            url = f"{self._get_base_url()}/api/session/conversations/{conversation_id}/messages"
            headers = {
                "X-Owner-Type": str(owner_type),
                "X-Owner-Id": str(owner_id),
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    # Java 返回格式: {data: {records: [...]}}
                    records = data.get("data", {}).get("records", [])
                    return records
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
