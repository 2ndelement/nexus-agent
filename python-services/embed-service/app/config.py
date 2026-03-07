"""
app/config.py — Embed Service 配置
"""
from __future__ import annotations
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8014  # 改为 8014，避免与 Java session-service 冲突

    # Embedding 模型
    embedding_model: str = "BAAI/bge-base-zh-v1.5"
    embedding_dim: int = 768
    embedding_batch_size: int = 32

    # 缓存配置
    cache_enabled: bool = True
    cache_max_size: int = 10000  # 最大缓存条目数

    # 日志
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
