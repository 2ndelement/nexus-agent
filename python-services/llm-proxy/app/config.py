"""
app/config.py — 从环境变量读取配置（无硬编码密钥）

多模型路由配置示例（LLM_PROVIDERS_JSON 环境变量）：
{
  "MiniMax-M2.5-highspeed": {
    "base_url": "https://copilot.lab.2ndelement.tech/v1",
    "api_key": "your-key",
    "model": "MiniMax-M2.5-highspeed"
  },
  "gpt-4o": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "sk-xxx",
    "model": "gpt-4o"
  }
}
"""
from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class ProviderConfig:
    """单个 LLM Provider 配置，不使用 Pydantic 以避免嵌套 Settings 冲突。"""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def __repr__(self) -> str:
        return f"ProviderConfig(model={self.model!r}, base_url={self.base_url!r})"


class Settings(BaseSettings):
    """所有配置来自环境变量或 .env.dev 文件，严禁硬编码密钥。"""

    model_config = SettingsConfigDict(
        env_file=".env.dev",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 默认 Provider（无法从 LLM_PROVIDERS_JSON 匹配时使用） ──
    llm_default_model: str = "MiniMax-M2.5-highspeed"
    llm_default_base_url: str = "https://copilot.lab.2ndelement.tech/v1"
    llm_default_api_key: str = ""

    # ── 多 Provider JSON 配置 ──
    # 格式: {"model-name": {"base_url": "...", "api_key": "...", "model": "..."}}
    llm_providers_json: str = ""

    # ── 通用 LLM 参数 ──
    llm_timeout: float = 60.0  # 请求超时（秒）

    # ── 服务配置 ──
    llm_proxy_port: int = 8010
    # Redis（Token 统计持久化）
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379

    log_level: str = "INFO"

    # ── 解析后的 providers 字典（内部使用，不来自环境变量） ──
    _providers: dict[str, ProviderConfig] = {}

    @model_validator(mode="after")
    def _parse_providers(self) -> "Settings":
        """解析 LLM_PROVIDERS_JSON 并合并默认 Provider。"""
        providers: dict[str, ProviderConfig] = {}

        # 解析 JSON 多 Provider 配置
        if self.llm_providers_json:
            try:
                raw: dict[str, Any] = json.loads(self.llm_providers_json)
                for model_key, cfg in raw.items():
                    providers[model_key] = ProviderConfig(
                        base_url=cfg["base_url"],
                        api_key=cfg["api_key"],
                        model=cfg.get("model", model_key),
                    )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("LLM_PROVIDERS_JSON 解析失败，忽略: %s", e)

        # 确保默认 model 始终在路由表中
        if self.llm_default_model not in providers:
            providers[self.llm_default_model] = ProviderConfig(
                base_url=self.llm_default_base_url,
                api_key=self.llm_default_api_key,
                model=self.llm_default_model,
            )

        object.__setattr__(self, "_providers", providers)
        return self

    def get_provider(self, model: str | None = None) -> ProviderConfig:
        """
        根据 model 名称返回对应的 ProviderConfig。

        路由规则：
        1. model 在 providers 表中 → 返回对应 provider
        2. model 不在表中但有值 → 使用默认 provider，model 字段替换为请求值
        3. model 为 None → 使用默认 provider
        """
        providers: dict[str, ProviderConfig] = object.__getattribute__(self, "_providers")

        if model and model in providers:
            return providers[model]

        # 默认 provider
        default = ProviderConfig(
            base_url=self.llm_default_base_url,
            api_key=self.llm_default_api_key,
            model=model or self.llm_default_model,
        )
        return default

    def list_models(self) -> list[str]:
        """返回所有已配置的 model 名称列表。"""
        providers: dict[str, ProviderConfig] = object.__getattribute__(self, "_providers")
        return list(providers.keys())


# 单例
settings = Settings()
