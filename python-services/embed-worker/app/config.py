"""
app/config.py — embed-worker 配置
"""
from __future__ import annotations
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    embed_queue: str = "nexus.embed.tasks"
    embed_result_exchange: str = "nexus.embed.results"

    # Embed Service（推荐：使用独立的 Embed Service）
    embed_service_url: str = "http://127.0.0.1:8004"
    use_embed_service: bool = True  # 是否使用独立的 Embed Service

    # Milvus（向量库）
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_uri: str = ""  # 空时使用 host:port 构造

    # ChromaDB（备用）
    chroma_persist_directory: str = "./data/chroma"
    vector_store_backend: str = "chroma"  # "milvus" | "chroma"

    # 运行配置
    worker_concurrency: int = 2
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
