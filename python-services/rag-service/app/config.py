"""
app/config.py — RAG Service 配置
所有配置项来自环境变量，无硬编码密钥。
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.dev",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Service
    rag_service_port: int = 8003
    log_level: str = "INFO"

    # ChromaDB
    chroma_mode: str = "memory"          # "memory" | "persistent"
    chroma_persist_dir: str = "./chroma_data"

    # Embedding
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384             # 与上述模型匹配

    # Retrieval defaults
    default_top_k: int = 5
    rrf_k: int = 60                      # RRF 常数，一般取 60
    bm25_top_k_factor: int = 3           # BM25 候选集 = top_k * factor


settings = Settings()
