"""
app/retriever/hybrid.py — BM25 + 向量 RRF 混合检索

RRF (Reciprocal Rank Fusion) 公式：
    score(d) = Σ  1 / (k + rank(d, list_i) + 1)
其中 k=60 是平滑常数（SIGIR 2009 Cormack et al.）。

流程：
1. 从 ChromaDB 拉取全量 chunks（用于 BM25 索引）
2. BM25 检索 top_k*bm25_factor 候选
3. 向量检索 top_k*bm25_factor 候选
4. RRF 融合两路结果
5. 返回融合后 top_k 结果
"""
from __future__ import annotations

import logging
from typing import Any

from rank_bm25 import BM25Okapi

from app.embedder import BaseEmbedder
from app.retriever.base import BaseRetriever, RetrievedChunk

logger = logging.getLogger(__name__)


# ─────────────────────────── RRF 核心 ───────────────────────────

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


# ─────────────────────────── BM25 检索 ───────────────────────────

def _tokenize(text: str) -> list[str]:
    """
    简单分词：保留汉字序列和英文单词。
    中文按字切分，英文按空格/标点切分。
    """
    import re
    # 保留汉字、英文字母数字
    tokens: list[str] = []
    # 中文字符逐字
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            tokens.append(char)
    # 英文单词
    words = re.findall(r'[a-zA-Z0-9]+', text.lower())
    tokens.extend(words)
    return tokens or [text]  # fallback：避免空 token 列表


def bm25_search(
    query: str,
    all_chunks: list[RetrievedChunk],
    top_k: int,
) -> list[str]:
    """
    使用 BM25Okapi 对 all_chunks 做关键词检索。

    Args:
        query:      查询文本。
        all_chunks: 全量 chunk 列表（已从 ChromaDB 拉取）。
        top_k:      返回候选数。

    Returns:
        chunk_id 列表，按 BM25 分数降序。
    """
    if not all_chunks:
        return []

    tokenized_corpus = [_tokenize(c.content) for c in all_chunks]
    bm25 = BM25Okapi(tokenized_corpus)

    query_tokens = _tokenize(query)
    scores = bm25.get_scores(query_tokens)

    # 按分数降序排列，取前 top_k
    ranked = sorted(
        range(len(all_chunks)),
        key=lambda i: -scores[i],
    )[:top_k]

    return [all_chunks[i].chunk_id for i in ranked]


# ─────────────────────────── 混合检索器 ───────────────────────────

class HybridRetriever:
    """
    BM25 + 向量混合检索，使用 RRF 融合两路排序。

    依赖：
        retriever: BaseRetriever（通常是 ChromaRetriever）
        embedder:  BaseEmbedder（生产用 SentenceTransformer，测试用 Mock）
    """

    def __init__(
        self,
        retriever: BaseRetriever,
        embedder: BaseEmbedder,
        rrf_k: int = 60,
        candidate_factor: int = 3,
    ):
        self._retriever = retriever
        self._embedder = embedder
        self._rrf_k = rrf_k
        self._candidate_factor = candidate_factor  # 候选集倍数

    def retrieve(
        self,
        tenant_id: str,
        kb_id: str,
        query: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """
        混合检索入口。

        1. 拉取全量 chunks（BM25 需要全文）
        2. BM25 检索 candidate_k 个候选
        3. 向量检索 candidate_k 个候选
        4. RRF 融合
        5. 返回 top_k 结果

        Args:
            tenant_id: 租户 ID。
            kb_id:     知识库 ID。
            query:     查询文本。
            top_k:     最终返回数量。

        Returns:
            按 RRF 分数降序的 RetrievedChunk 列表。
        """
        candidate_k = top_k * self._candidate_factor

        # ── 1. 获取全量 chunks（供 BM25）──
        all_chunks = self._retriever.get_all_chunks(tenant_id, kb_id)
        if not all_chunks:
            logger.debug("hybrid retrieve: no chunks in kb=%s tenant=%s", kb_id, tenant_id)
            return []

        chunk_map: dict[str, RetrievedChunk] = {c.chunk_id: c for c in all_chunks}

        # ── 2. BM25 检索 ──
        bm25_ids = bm25_search(query, all_chunks, top_k=candidate_k)

        # ── 3. 向量检索 ──
        query_embedding = self._embedder.embed_query(query)
        vector_chunks = self._retriever.vector_search(
            tenant_id, kb_id, query_embedding, top_k=candidate_k
        )
        vector_ids = [c.chunk_id for c in vector_chunks]
        # 用向量检索的 score 更新 chunk_map（更精确）
        for vc in vector_chunks:
            if vc.chunk_id in chunk_map:
                chunk_map[vc.chunk_id].score = vc.score

        # ── 4. RRF 融合 ──
        fused = rrf_merge(bm25_ids, vector_ids, k=self._rrf_k)

        # ── 5. 组装最终结果 ──
        results: list[RetrievedChunk] = []
        for chunk_id, rrf_score in fused[:top_k]:
            if chunk_id not in chunk_map:
                continue
            chunk = chunk_map[chunk_id]
            # 用 RRF 分数作为最终 score
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    doc_id=chunk.doc_id,
                    content=chunk.content,
                    score=round(rrf_score, 6),
                    metadata=chunk.metadata,
                )
            )

        logger.debug(
            "hybrid retrieve: tenant=%s, kb=%s, query='%s', results=%d",
            tenant_id, kb_id, query[:30], len(results),
        )
        return results
