"""
app/reranker.py — Rerank 重排模块

二阶段检索：
1. 第一阶段：向量检索（召回 top_k * rerank_factor 条）
2. 第二阶段：Rerank 重排（精排到 top_k 条）

为什么取更多候选？
- 向量检索可能遗漏相关文档
- Rerank 模型更精准，但计算成本高
- 取 3-5 倍候选，平衡召回和精度
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RerankedResult:
    """重排后的结果"""
    chunk_id: str
    doc_id: str
    content: str
    score: float  # Rerank 分数
    rank: int    # 重排后的排名


class BaseReranker(ABC):
    """Reranker 抽象基类"""

    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int = 5,
    ) -> list[RerankedResult]:
        pass


class BGERReranker(BaseReranker):
    """BGE Reranker - 使用 BAAI BGE Reranker 模型"""
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-base",
        device: str = "cpu",
    ):
        self._model_name = model_name
        self._device = device
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from FlagEmbedding import FlagReranker
                logger.info("加载 Reranker 模型: %s", self._model_name)
                self._model = FlagReranker(
                    model_name=self._model_name,
                    device=self._device,
                )
                logger.info("Reranker 模型加载完成")
            except ImportError:
                logger.warning("FlagEmbedding 未安装，使用 MockReranker")
                raise ImportError("pip install FlagEmbedding")

    def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int = 5,
    ) -> list[RerankedResult]:
        if not documents:
            return []
        
        self._load_model()
        
        doc_contents = [doc.get("content", "") for doc in documents]
        pairs = [(query, doc) for doc in doc_contents]
        scores = self._model.compute_score(pairs)
        
        results = []
        for i, (doc, score) in enumerate(zip(documents, scores)):
            results.append(RerankedResult(
                chunk_id=doc.get("chunk_id", ""),
                doc_id=doc.get("doc_id", ""),
                content=doc.get("content", ""),
                score=float(score),
                rank=0,
            ))
        
        results.sort(key=lambda x: x.score, reverse=True)
        
        for i, result in enumerate(results):
            result.rank = i + 1
        
        return results[:top_k]


class MockReranker(BaseReranker):
    """模拟 Reranker，用于测试"""
    
    def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int = 5,
    ) -> list[RerankedResult]:
        if not documents:
            return []
        
        results = []
        for i, doc in enumerate(documents):
            results.append(RerankedResult(
                chunk_id=doc.get("chunk_id", ""),
                doc_id=doc.get("doc_id", ""),
                content=doc.get("content", ""),
                score=1.0 / (i + 1),
                rank=i + 1,
            ))
        
        return results[:top_k]


# 全局单例
_reranker_instance: Optional[BaseReranker] = None


def get_reranker() -> BaseReranker:
    global _reranker_instance
    if _reranker_instance is None:
        from app.config import settings
        try:
            _reranker_instance = BGERReranker(model_name=settings.reranker_model)
        except Exception as e:
            logger.warning(f"Reranker 初始化失败，使用 Mock: {e}")
            _reranker_instance = MockReranker()
    return _reranker_instance


def set_reranker(reranker: BaseReranker) -> None:
    global _reranker_instance
    _reranker_instance = reranker
