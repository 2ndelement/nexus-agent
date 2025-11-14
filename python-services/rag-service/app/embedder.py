"""
app/embedder.py — Embedding 工具

生产：使用 sentence-transformers（本地模型，无需 API Key）
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

# ─────────────────────────── 抽象基类 ───────────────────────────

class BaseEmbedder(ABC):
    """Embedding 抽象基类，支持依赖注入。"""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量 embed 文本列表。返回 list[vector]。"""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """embed 单个查询文本。"""

    @property
    @abstractmethod
    def dim(self) -> int:
        """向量维度。"""


# ─────────────────────────── 生产实现 ───────────────────────────

class SentenceTransformerEmbedder(BaseEmbedder):
    """
    基于 sentence-transformers 的 Embedder。
    懒加载：首次调用时才加载模型（避免进程启动时就触发模型下载）。
    """

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self._model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _load_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer
                    logger.info("加载 Embedding 模型: %s", self._model_name)
                    self._model = SentenceTransformer(self._model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self._load_model()
        vectors = self._model.encode(texts, convert_to_numpy=True)
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        self._load_model()
        vector = self._model.encode([text], convert_to_numpy=True)
        return vector[0].tolist()

    @property
    def dim(self) -> int:
        return 384  # paraphrase-multilingual-MiniLM-L12-v2


# ─────────────────────────── 测试 Mock ───────────────────────────

class MockEmbedder(BaseEmbedder):
    """
    随机向量 Embedder，用于测试。
    不下载任何模型，不访问网络。

    为了让"相似文本返回相似向量"的语义测试能工作，
    使用固定 seed 的哈希确定性映射：
    相同文本 → 相同向量（但不同文本也可能相似，测试时注意构造差异够大的用例）。
    """

    def __init__(self, dim: int = 64, seed: int = 42):
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


# ─────────────────────────── 全局单例管理 ───────────────────────────

_embedder_instance: BaseEmbedder | None = None
_embedder_lock = threading.Lock()


def get_embedder() -> BaseEmbedder:
    """获取全局 Embedder 单例（懒初始化）。"""
    global _embedder_instance
    if _embedder_instance is None:
        with _embedder_lock:
            if _embedder_instance is None:
                from app.config import settings
                _embedder_instance = SentenceTransformerEmbedder(settings.embedding_model)
    return _embedder_instance


def set_embedder(embedder: BaseEmbedder) -> None:
    """替换全局 Embedder（主要用于测试注入 MockEmbedder）。"""
    global _embedder_instance
    _embedder_instance = embedder


def reset_embedder() -> None:
    """重置全局 Embedder（测试清理用）。"""
    global _embedder_instance
    _embedder_instance = None
