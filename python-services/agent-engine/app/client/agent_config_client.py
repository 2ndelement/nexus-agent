"""
app/client/agent_config_client.py — 直连 MySQL 获取 Agent 配置

功能：
- 根据 agent_id 和 tenant_id 获取 Agent 配置
- 缓存配置避免重复查询
- 返回 system_prompt、model、temperature 等配置项
"""
from __future__ import annotations

import logging
from typing import Optional

import aiomysql

logger = logging.getLogger(__name__)


# 系统默认 Agent 配置（当用户没有可用 Agent 时使用）
SYSTEM_DEFAULT_AGENT = {
    "id": "system-default",
    "name": "系统助手",
    "description": "系统默认的 AI 助手",
    "system_prompt": "你是一个友好、有帮助的 AI 助手。请用清晰简洁的语言回答用户的问题。",
    "model": None,  # 使用服务默认模型
    "temperature": None,  # 使用服务默认温度
    "max_tokens": None,
    "tools_enabled": None,
    "knowledge_base_ids": None,
}


class AgentConfigClient:
    """
    直接从 MySQL 获取 Agent 配置（最简高效方案）

    缓存策略：
    - 使用内存缓存，key 为 agent_id
    - 配置更新时需手动清除缓存
    """

    def __init__(self):
        self._cache: dict[int, dict] = {}
        self._pool: Optional[aiomysql.Pool] = None

    async def _get_pool(self) -> aiomysql.Pool:
        """获取数据库连接池"""
        if self._pool is None:
            from app.config import settings
            self._pool = await aiomysql.create_pool(
                host=settings.mysql_host,
                port=settings.mysql_port,
                user=settings.mysql_user,
                password=settings.mysql_pass,
                db=settings.mysql_db,
                autocommit=True,
                minsize=1,
                maxsize=5,
            )
            logger.info(f"[AgentConfigClient] 数据库连接池已创建: {settings.mysql_host}:{settings.mysql_port}/{settings.mysql_db}")
        return self._pool

    async def get_agent_config(self, agent_id: int, tenant_id: str) -> Optional[dict]:
        """
        获取 Agent 配置

        Args:
            agent_id: Agent 配置 ID
            tenant_id: 租户 ID（用于多租户隔离验证）

        Returns:
            Agent 配置字典，包含:
            - id: Agent ID
            - name: Agent 名称
            - system_prompt: 系统提示词
            - model: 模型名称
            - temperature: 温度参数
            - max_tokens: 最大 token 数
            - tools_enabled: 启用的工具列表（JSON 字符串）
        """
        # 检查缓存
        cache_key = agent_id
        if cache_key in self._cache:
            logger.debug(f"[AgentConfigClient] 命中缓存: agent_id={agent_id}")
            return self._cache[cache_key]

        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT id, name, description, system_prompt, model,
                               temperature, max_tokens, tools_enabled, knowledge_base_ids
                        FROM agent_config
                        WHERE id = %s AND tenant_id = %s AND status = 1
                        """,
                        (agent_id, tenant_id)
                    )
                    row = await cur.fetchone()

                    if row:
                        config = dict(row)
                        self._cache[cache_key] = config
                        logger.info(
                            f"[AgentConfigClient] 获取配置成功: agent_id={agent_id}, "
                            f"name={config.get('name')}, has_system_prompt={bool(config.get('system_prompt'))}"
                        )
                        return config
                    else:
                        logger.warning(f"[AgentConfigClient] 未找到配置: agent_id={agent_id}, tenant_id={tenant_id}")
                        return None

        except Exception as e:
            logger.error(f"[AgentConfigClient] 获取配置失败: agent_id={agent_id}, error={e}")
            return None

    async def get_default_agent_config(self, tenant_id: str) -> Optional[dict]:
        """
        获取租户的默认 Agent 配置（第一个可用的 Agent）

        Args:
            tenant_id: 租户 ID

        Returns:
            Agent 配置字典，或 None
        """
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT id, name, description, system_prompt, model,
                               temperature, max_tokens, tools_enabled, knowledge_base_ids
                        FROM agent_config
                        WHERE tenant_id = %s AND status = 1
                        ORDER BY id ASC
                        LIMIT 1
                        """,
                        (tenant_id,)
                    )
                    row = await cur.fetchone()

                    if row:
                        config = dict(row)
                        logger.info(
                            f"[AgentConfigClient] 获取默认配置: tenant_id={tenant_id}, "
                            f"agent_id={config.get('id')}, name={config.get('name')}"
                        )
                        return config
                    else:
                        # 无可用 Agent 时返回系统默认配置
                        logger.info(f"[AgentConfigClient] 租户无可用 Agent，使用系统默认配置: tenant_id={tenant_id}")
                        return SYSTEM_DEFAULT_AGENT.copy()

        except Exception as e:
            # 数据库错误时也返回系统默认配置，保证服务可用
            logger.error(f"[AgentConfigClient] 获取默认配置失败，使用系统默认: tenant_id={tenant_id}, error={e}")
            return SYSTEM_DEFAULT_AGENT.copy()

    def clear_cache(self, agent_id: int = None):
        """
        清除缓存

        Args:
            agent_id: 指定 Agent ID，None 则清除全部
        """
        if agent_id is not None:
            self._cache.pop(agent_id, None)
            logger.debug(f"[AgentConfigClient] 清除缓存: agent_id={agent_id}")
        else:
            self._cache.clear()
            logger.debug("[AgentConfigClient] 清除全部缓存")

    async def close(self):
        """关闭数据库连接池"""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
            logger.info("[AgentConfigClient] 数据库连接池已关闭")


# 全局单例
_agent_config_client: Optional[AgentConfigClient] = None


def get_agent_config_client() -> AgentConfigClient:
    """获取 Agent 配置客户端单例"""
    global _agent_config_client
    if _agent_config_client is None:
        _agent_config_client = AgentConfigClient()
    return _agent_config_client
