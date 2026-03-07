"""
app/embedder.py — Embedding 工具

生产：使用 BGE 中文Embedding模型
测试：可注入 MockEmbedder（随机向量，不下载模型）

设计模式：依赖注入，通过 get_embedder() 获取单例。
测试时调用 set_embedder(MockEmbedder()) 替换。
"""
from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod

import numpy as np

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════ 抽象基类 ═══════════════════════════════════════════════════════════════════

class BaseEmbedder(ABC):
    """Embedding 抽象基类，支持依赖注入。"""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量 embed 文本列表，返回 list[vector]。"""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """embed 单个查询文本。"""

    @property
    @abstractmethod
    def dim(self) -> int:
        """向量维度。"""


# ═══════════════════════════════════════════════════════════════════ 生产实现 ═══════════════════════════════════════════════════════════════════

class BGEEmbedder(BaseEmbedder):
    """
    基于 BGE (BAAI General Embedding) 的 Embedder。
    
    推荐模型：
    - bge-large-zh-v1.5   (1024维，效果最好)
    - bge-base-zh-v1.5    (768维，平衡)
    - bge-small-zh-v1.5   (512维，最快)
    - bge-m3              (1024维，多语言)
    
    懒加载：首次调用时才加载模型（避免进程启动时卡顿）。
    """

    def __init__(
        self, 
        model_name: str = "BAAI/bge-base-zh-v1.5",
        normalize: bool = True,
        max_length: int = 512,
    ):
        self._model_name = model_name
        self._normalize = normalize
        self._max_length = max_length
        self._model = None
        self._lock = threading.Lock()

    def _load_model(self):
        """懒加载模型"""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                        logger.info("加载 Embedding 模型: %s", self._model_name)
                        self._model = SentenceTransformer(self._model_name)
                        logger.info("模型加载完成，维度: %d", self.dim)
                    except ImportError:
                        logger.error("sentence-transformers 未安装，请运行: pip install sentence-transformers")
                        raise

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self._load_model()
        # 批量编码
        embeddings = self._model.encode(
            texts,
            batch_size=32,
            normalize_embeddings=self._normalize,
            truncate_dim=self._max_length,
            convert_to_numpy=True,
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        self._load_model()
        embedding = self._model.encode(
            [text],
            normalize_embeddings=self._normalize,
            truncate_dim=self._max_length,
            convert_to_numpy=True,
        )
        return embedding[0].tolist()

    @property
    def dim(self) -> int:
        """根据模型名称返回维度"""
        if "large" in self._model_name.lower():
            return 1024
        elif "small" in self._model_name.lower():
            return 512
        else:  # base
            return 768


# 向后兼容：保留旧名称
class SentenceTransformerEmbedder(BGEEmbedder):
    """向后兼容的别名"""
    pass


# ═══════════════════════════════════════════════════════════════════ 测试 Mock ═══════════════════════════════════════════════════════════════════

class MockEmbedder(BaseEmbedder):
    """
    随机向量 Embedder，用于测试。
    不下载任何模型，不访问网络。
    
    为了让"相似文本返回相似向量"的语义测试能工作，
    使用固定 seed 的哈希确定映射：相同文本 → 相同向量（但不同文本也可能相似，测试时注意语义差异大的用例）。
    """

    def __init__(self, dim: int = 768, seed: int = 42):
        self._dim = dim
        self._seed = seed

    def _text_to_vector(self, text: str) -> list[float]:
        """将文本确定性地映射到单位向量。"""
        # 用文本哈希作为随机种子，保证相同文本→相同向量
        h = hash(text) % (2**31)
        rng = np.random.RandomState(h)
        v = rng.randn(self._dim).astype(np.float32)
        norm = np.linalg.norm(v)
        if norm > 0:
            v = v / norm
        return v.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._text_to_vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._text_to_vector(text)

    @property
    def dim(self) -> int:
        return self._dim


# ═══════════════════════════════════════════════════════════════════ 全局单例管理 ═══════════════════════════════════════════════════════════════════

_embedder_instance: BaseEmbedder | None = None
_embedder_lock = threading.Lock()


def get_embedder() -> BaseEmbedder:
    """获取全局 Embedder 单例（懒初始化）。"""
    global _embedder_instance
    if _embedder_instance is None:
        with _embedder_lock:
            if _embedder_instance is None:
                from app.rag_config import settings
                _embedder_instance = BGEEmbedder(settings.embedding_model)
    return _embedder_instance


def set_embedder(embedder: BaseEmbedder) -> None:
    """替换全局 Embedder（主要用于测试注入 MockEmbedder）。"""
    global _embedder_instance
    _embedder_instance = embedder


def reset_embedder() -> None:
    """重置全局 Embedder（测试清理用）。"""
    global _embedder_instance
    _embedder_instance = None
