"""
app/config.py — 配置
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """所有配置项均从环境变量或 .env 读取"""

    # 服务
    host: str = "0.0.0.0"
    port: int = 8013

    # ChromaDB
    chroma_persist_directory: str = "./data/chroma"

    # Embedding
    # 可选模型：
    # - BAAI/bge-large-zh-v1.5 (1024维，效果最好)
    # - BAAI/bge-base-zh-v1.5  (768维，平衡)  
    # - BAAI/bge-small-zh-v1.5  (512维，最快)
    embedding_model: str = "BAAI/bge-base-zh-v1.5"

    # Reranker (可选)
    # - BAAI/bge-reranker-base
    # - BAAI/bge-reranker-large
    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_top_k: int = 5  # 重排后取前5条

    # 分块
    chunk_size: int = 1000
    chunk_overlap: int = 150

    # 日志
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
