"""
app/embedder.py — Embedding 封装

与 rag-service 共用相同的接口约定，
生产使用 SentenceTransformer，测试可注入 MockEmbedder。
"""
from __future__ import annotations
import logging
import threading
from abc import ABC, abstractmethod

import numpy as np

logger = logging.getLogger(__name__)


class BaseEmbedder(ABC):
    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]: ...

    @property
    @abstractmethod
    def dim(self) -> int: ...


class SentenceTransformerEmbedder(BaseEmbedder):
    """
    生产 Embedder：paraphrase-multilingual-MiniLM-L12-v2 (384维)
    懒加载，首次调用才下载/加载模型。
    """
    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self._model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer
                    logger.info("加载 Embedding 模型: %s", self._model_name)
                    self._model = SentenceTransformer(self._model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self._load()
        vecs = self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return vecs.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    @property
    def dim(self) -> int:
        return 384


class MockEmbedder(BaseEmbedder):
    """测试用 Embedder，不加载模型，相同文本 → 相同向量（确定性）"""
    def __init__(self, dim: int = 64):
        self._dim = dim

    def _vec(self, text: str) -> list[float]:
        h = hash(text) % (2 ** 31)
        rng = np.random.RandomState(h)
        v = rng.randn(self._dim).astype(np.float32)
        norm = np.linalg.norm(v)
        return (v / norm if norm > 0 else v).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)

    @property
    def dim(self) -> int:
        return self._dim
