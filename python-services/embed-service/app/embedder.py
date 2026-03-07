"""
app/embedder.py — BGE Embedding 模型封装

单例模式，支持 LRU 缓存。
"""
from __future__ import annotations

import hashlib
import logging
import threading
from collections import OrderedDict
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class BGEEmbedder:
    """BGE Embedding 模型"""

    def __init__(self, model_name: str = "BAAI/bge-base-zh-v1.5"):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

        # LRU 缓存
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._cache_max_size = settings.cache_max_size
        self._cache_enabled = settings.cache_enabled

    def _load_model(self):
        """懒加载模型"""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    logger.info(f"加载 Embedding 模型: {self.model_name}")
                    from sentence_transformers import SentenceTransformer
                    self._model = SentenceTransformer(self.model_name)
                    logger.info(f"模型加载完成，维度: {self._model.get_sentence_embedding_dimension()}")

    @property
    def dim(self) -> int:
        """获取向量维度"""
        self._load_model()
        return self._model.get_sentence_embedding_dimension()

    def _get_cache_key(self, text: str) -> str:
        """生成缓存 key"""
        return hashlib.md5(text.encode()).hexdigest()

    def _get_from_cache(self, text: str) -> Optional[list[float]]:
        """从缓存获取"""
        if not self._cache_enabled:
            return None
        key = self._get_cache_key(text)
        if key in self._cache:
            # 移到末尾（LRU）
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _put_to_cache(self, text: str, embedding: list[float]):
        """写入缓存"""
        if not self._cache_enabled:
            return
        key = self._get_cache_key(text)
        self._cache[key] = embedding
        self._cache.move_to_end(key)
        # 淘汰旧条目
        while len(self._cache) > self._cache_max_size:
            self._cache.popitem(last=False)

    def embed_query(self, text: str) -> tuple[list[float], bool]:
        """
        查询向量化

        Returns:
            (embedding, cached): 向量和是否来自缓存
        """
        # 尝试从缓存获取
        cached = self._get_from_cache(text)
        if cached is not None:
            return cached, True

        # 计算 embedding
        self._load_model()
        embedding = self._model.encode(
            text,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()

        # 写入缓存
        self._put_to_cache(text, embedding)
        return embedding, False

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量文档向量化"""
        if not texts:
            return []

        self._load_model()
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=settings.embedding_batch_size,
            show_progress_bar=True,
        ).tolist()

        # 写入缓存
        for text, emb in zip(texts, embeddings):
            self._put_to_cache(text, emb)

        return embeddings

    def cache_stats(self) -> dict:
        """缓存统计"""
        return {
            "enabled": self._cache_enabled,
            "size": len(self._cache),
            "max_size": self._cache_max_size,
        }


# 全局单例
_embedder_instance: Optional[BGEEmbedder] = None
_embedder_lock = threading.Lock()


def get_embedder() -> BGEEmbedder:
    """获取全局 Embedder 单例"""
    global _embedder_instance
    if _embedder_instance is None:
        with _embedder_lock:
            if _embedder_instance is None:
                _embedder_instance = BGEEmbedder(settings.embedding_model)
    return _embedder_instance
