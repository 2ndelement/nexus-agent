"""
app/retriever/hybrid.py — BM25 + 向量 RRF 混合检索

现在完全基于 Milvus 原生实现：
1. 稠密向量 (Dense Vector) - SentenceTransformer 语义嵌入
2. 稀疏向量 (Sparse Vector) - Milvus 原生 TF-IDF
3. 混合检索 - RRF (Reciprocal Rank Fusion) 融合
4. Re-Rank - Cross-Encoder 重排序

Author: 帕托莉 🐱
"""

from __future__ import annotations

import logging
from typing import Any

from app.embedder import BaseEmbedder
from app.retriever.base import RetrievedChunk
from app.retriever.milvus_retriever import (
    MilvusRetriever,
    MilvusRetrieverConfig,
    SparseVectorGenerator,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════════
# RRF 核心
# ═══════════════════════════════════════════════════════════════════════════════════

def rrf_merge(
    bm25_ranked_ids: list[str],
    vector_ranked_ids: list[str],
    k: int = 60,
) -> list[tuple[str, float]]:
    """
    Reciprocal Rank Fusion。

    Args:
        bm25_ranked_ids:   BM25 结果的 chunk_id 列表（按相关性降序）。
        vector_ranked_ids: 向量检索结果的 chunk_id 列表（按相关性降序）。
        k:                 RRF 平滑常数，默认 60。

    Returns:
        list of (chunk_id, rrf_score)，按 rrf_score 降序。
    """
    scores: dict[str, float] = {}

    for rank, doc_id in enumerate(bm25_ranked_ids):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

    for rank, doc_id in enumerate(vector_ranked_ids):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

    return sorted(scores.items(), key=lambda x: -x[1])


# ═══════════════════════════════════════════════════════════════════════════════════
# 混合检索器 (封装 MilvusRetriever)
# ═══════════════════════════════════════════════════════════════════════════════════

class HybridRetriever:
    """
    混合检索器 - 基于 Milvus 原生实现

    支持：
    - 稠密向量语义检索
    - 稀疏向量关键词检索 (TF-IDF)
    - RRF 融合
    - Re-Rank 重排序

    依赖：
        retriever: MilvusRetriever
        embedder:  BaseEmbedder
    """

    def __init__(
        self,
        retriever: MilvusRetriever,
        embedder: BaseEmbedder,
        rrf_k: int = 60,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5,
    ):
        """
        初始化混合检索器

        Args:
            retriever: MilvusRetriever 实例
            embedder:  Embedder 实例 (用于生成查询向量)
            rrf_k:     RRF 平滑常数
            dense_weight: 稠密向量权重
            sparse_weight: 稀疏向量权重
        """
        self._retriever = retriever
        self._embedder = embedder
        self._rrf_k = rrf_k
        self._dense_weight = dense_weight
        self._sparse_weight = sparse_weight

    def retrieve(
        self,
        tenant_id: str,
        kb_id: str,
        query: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """
        混合检索入口

        流程：
        1. 生成查询向量 (稠密 + 稀疏)
        2. Milvus 混合检索
        3. Re-Rank (可选)
        4. 返回结果

        Args:
            tenant_id: 租户 ID
            kb_id:     知识库 ID
            query:     查询文本
            top_k:     返回数量

        Returns:
            按 RRF 分数降序的 RetrievedChunk 列表
        """
        # 生成查询向量
        query_embedding = self._embedder.embed_query(query)

        # 调用 Milvus 混合检索
        results = self._retriever.hybrid_search(
            tenant_id=tenant_id,
            kb_id=kb_id,
            query_text=query,
            query_embedding=query_embedding,
            top_k=top_k,
            use_sparse=True,
            use_rerank=True,
        )

        logger.debug(
            "hybrid retrieve: tenant=%s, kb=%s, query='%s', results=%d",
            tenant_id, kb_id, query[:30], len(results),
        )

        return results

    def dense_only(
        self,
        tenant_id: str,
        kb_id: str,
        query: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """
        仅稠密向量检索 (快速但不包含关键词匹配)
        """
        query_embedding = self._embedder.embed_query(query)

        return self._retriever.hybrid_search(
            tenant_id=tenant_id,
            kb_id=kb_id,
            query_text=query,
            query_embedding=query_embedding,
            top_k=top_k,
            use_sparse=False,
            use_rerank=False,
        )

    def sparse_only(
        self,
        tenant_id: str,
        kb_id: str,
        query: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """
        仅稀疏向量检索 (关键词匹配，不包含语义理解)
        """
        query_embedding = self._embedder.embed_query(query)  # 需要一个 dummy

        return self._retriever.hybrid_search(
            tenant_id=tenant_id,
            kb_id=kb_id,
            query_text=query,
            query_embedding=query_embedding,
            top_k=top_k,
            use_sparse=True,
            use_rerank=False,
        )


# ═══════════════════════════════════════════════════════════════════════════════════
# 便捷工厂函数
# ═══════════════════════════════════════════════════════════════════════════════════

def create_milvus_hybrid_retriever(
    milvus_host: str = "localhost",
    milvus_port: int = 19530,
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2",
    rerank_model: str = "BAAI/bge-reranker-base",
    dense_weight: float = 0.5,
    sparse_weight: float = 0.5,
) -> HybridRetriever:
    """
    便捷工厂函数：创建 Milvus 混合检索器

    Args:
        milvus_host: Milvus 服务地址
        milvus_port: Milvus 服务端口
        embedding_model: Embedding 模型名称
        rerank_model: Re-Rank 模型名称
        dense_weight: 稠密向量权重
        sparse_weight: 稀疏向量权重

    Returns:
        HybridRetriever 实例
    """
    from app.embedder import SentenceTransformerEmbedder
    from app.retriever.milvus_retriever import MilvusConfig, MilvusRetrieverConfig

    # 配置
    milvus_config = MilvusConfig(
        host=milvus_host,
        port=milvus_port,
    )

    retriever_config = MilvusRetrieverConfig(
        milvus_config=milvus_config,
        use_sparse=True,
        use_rerank=True,
        rerank_model=rerank_model,
        dense_weight=dense_weight,
        sparse_weight=sparse_weight,
    )

    # Embedder
    embedder = SentenceTransformerEmbedder(model_name=embedding_model)

    # Retriever
    retriever = MilvusRetriever(
        config=retriever_config,
        embedder=embedder,
    )

    return HybridRetriever(
        retriever=retriever,
        embedder=embedder,
        dense_weight=dense_weight,
        sparse_weight=sparse_weight,
    )
