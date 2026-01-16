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

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8100
    chroma_persist_path: str = "/data/chroma"
    chroma_mode: str = "http"          # "http" | "persistent" | "memory"

    # Embedding 模型
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    embedding_batch_size: int = 32     # 每批 embed 的 chunk 数

    # 运行配置
    worker_concurrency: int = 2        # 同时处理的消息数
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
