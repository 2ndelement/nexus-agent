"""
app/config.py — RAG Service 配置

支持两种向量存储后端：
- ChromaDB (默认，开发测试用)
- Milvus (生产环境推荐)

Author: 帕托莉 🐱
"""

from __future__ import annotations

from enum import Enum
from pydantic_settings import BaseSettings


class VectorStoreBackend(str, Enum):
    """向量存储后端"""
    CHROMA = "chroma"
    MILVUS = "milvus"


class Settings(BaseSettings):
    """
    所有配置项均从环境变量或 .env 文件读取
    """

    # ═══════════════════════════════════════════════════════════════════════════════════
    # 服务配置
    # ═══════════════════════════════════════════════════════════════════════════════════
    host: str = "0.0.0.0"
    rag_service_port: int = 8003

    # ═══════════════════════════════════════════════════════════════════════════════════
    # 🆕 向量存储后端选择
    # ═══════════════════════════════════════════════════════════════════════════════════
    vector_store_backend: VectorStoreBackend = VectorStoreBackend.CHROMA  # 默认使用 ChromaDB

    # ═══════════════════════════════════════════════════════════════════════════════════
    # 🆕 Milvus 配置 (Server 模式)
    # ═══════════════════════════════════════════════════════════════════════════════════
    # Milvus Server 模式：设置为 "http://host:port" 格式
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_uri: str = ""  # 空时使用 host:port 构造
    milvus_user: str = ""
    milvus_password: str = ""
    milvus_db: str = "default"

    # Milvus 索引配置
    milvus_index_type_dense: str = "IVF_FLAT"  # Lite 模式不支持 GPU，改用 IVF_FLAT
    milvus_index_type_sparse: str = "SPARSE_INVERTED_INDEX"
    milvus_metric_dense: str = "COSINE"
    milvus_metric_sparse: str = "IP"

    # ═══════════════════════════════════════════════════════════════════════════════════
    # ChromaDB 配置 (开发测试用)
    # ═══════════════════════════════════════════════════════════════════════════════════
    chroma_persist_directory: str = "./data/chroma"

    # ═══════════════════════════════════════════════════════════════════════════════════
    # Embedding 配置
    # ═══════════════════════════════════════════════════════════════════════════════════
    # 可选模型：
    # - BAAI/bge-large-zh-v1.5 (1024维，效果最好)
    # - BAAI/bge-base-zh-v1.5  (768维，平衡)
    # - BAAI/bge-small-zh-v1.5  (512维，最快)
    embedding_model: str = "BAAI/bge-base-zh-v1.5"

    # 嵌入维度 (必须与模型匹配)
    embedding_dim: int = 768

    # ═══════════════════════════════════════════════════════════════════════════════════
    # 🆕 稀疏向量配置
    # ═══════════════════════════════════════════════════════════════════════════════════
    use_sparse_vector: bool = True
    sparse_min_df: int = 1
    sparse_max_df: float = 0.95
    sparse_norm: str = "l2"

    # ═══════════════════════════════════════════════════════════════════════════════════
    # Reranker 配置
    # ═══════════════════════════════════════════════════════════════════════════════════
    # 可选模型：
    # - BAAI/bge-reranker-base
    # - BAAI/bge-reranker-large
    use_reranker: bool = True
    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_top_k: int = 10

    # ═══════════════════════════════════════════════════════════════════════════════════
    # 混合检索配置
    # ═══════════════════════════════════════════════════════════════════════════════════
    rrf_k: int = 60
    dense_weight: float = 0.5
    sparse_weight: float = 0.5
    candidate_factor: int = 3

    # ═══════════════════════════════════════════════════════════════════════════════════
    # 分块配置
    # ═══════════════════════════════════════════════════════════════════════════════════
    chunk_size: int = 1000
    chunk_overlap: int = 150

    # ═══════════════════════════════════════════════════════════════════════════════════
    # 日志
    # ═══════════════════════════════════════════════════════════════════════════════════
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
