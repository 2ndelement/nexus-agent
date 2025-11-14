"""
tests/test_hybrid.py — RRF 混合检索测试

覆盖场景：
1. rrf_merge 函数逻辑正确性
   - 只在一路出现的文档正确计分
   - 两路都出现的文档得分更高
   - 结果按分数降序
2. BM25 检索基本工作
3. 混合检索返回正确数量（top_k）
4. 混合检索 RRF 分数合并逻辑（两路均匹配 > 单路匹配）
5. 多租户隔离：检索结果只来自指定租户
6. 空知识库时返回空列表
"""
from __future__ import annotations

import chromadb
from chromadb.config import Settings
import numpy as np
import pytest

from app.embedder import MockEmbedder
from app.retriever.chroma_retriever import ChromaRetriever
from app.retriever.hybrid import HybridRetriever, rrf_merge, bm25_search, _tokenize
from app.retriever.base import RetrievedChunk
from app.chunker import chunk_document


# ─────────────────────────── Helper ───────────────────────────

def build_hybrid(dim: int = 64) -> tuple[HybridRetriever, ChromaRetriever, MockEmbedder]:
    client = chromadb.EphemeralClient(settings=Settings(allow_reset=True))
    embedder = MockEmbedder(dim=dim)
    retriever = ChromaRetriever(client=client)
    hybrid = HybridRetriever(
        retriever=retriever,
        embedder=embedder,
        rrf_k=60,
        candidate_factor=3,
    )
    return hybrid, retriever, embedder


def ingest(
    retriever: ChromaRetriever,
    embedder: MockEmbedder,
    tenant_id: str,
    kb_id: str,
    doc_id: str,
    content: str,
):
    chunks = chunk_document(doc_id=doc_id, content=content)
    embeddings = embedder.embed_documents([c.content for c in chunks])
    retriever.add_chunks(
        tenant_id=tenant_id,
        kb_id=kb_id,
        chunk_ids=[c.chunk_id for c in chunks],
        doc_ids=[c.doc_id for c in chunks],
        contents=[c.content for c in chunks],
        embeddings=embeddings,
        metadatas=[c.metadata for c in chunks],
    )
    return chunks


# ─────────────────────────── RRF 核心逻辑 ───────────────────────────

class TestRRFMerge:

    def test_rrf_both_lists_empty(self):
        """两路都为空 → 结果为空。"""
        result = rrf_merge([], [])
        assert result == []

    def test_rrf_only_bm25(self):
        """只有 BM25 一路结果。"""
        bm25 = ["doc1", "doc2", "doc3"]
        result = rrf_merge(bm25, [])
        ids = [r[0] for r in result]
        # doc1（rank=0）分数最高
        assert ids[0] == "doc1"
        assert ids[1] == "doc2"
        assert ids[2] == "doc3"

    def test_rrf_only_vector(self):
        """只有向量一路结果。"""
        vector = ["docA", "docB"]
        result = rrf_merge([], vector)
        assert result[0][0] == "docA"
        assert result[1][0] == "docB"

    def test_rrf_double_appearance_scores_higher(self):
        """
        同时出现在两路结果中的文档，得分高于只出现在一路的文档。

        bm25:   [shared, bm25-only]
        vector: [shared, vec-only]
        → shared 得分 = 1/(60+1) + 1/(60+1) > 单路文档
        """
        bm25 = ["shared", "bm25-only"]
        vector = ["shared", "vec-only"]
        result = rrf_merge(bm25, vector)
        scores = dict(result)

        assert scores["shared"] > scores["bm25-only"], (
            "两路出现的 doc 分数应 > 只在 BM25 出现的 doc"
        )
        assert scores["shared"] > scores["vec-only"], (
            "两路出现的 doc 分数应 > 只在向量检索出现的 doc"
        )

    def test_rrf_sorted_descending(self):
        """结果按分数降序排列。"""
        bm25 = ["a", "b", "c"]
        vector = ["a", "d", "e"]
        result = rrf_merge(bm25, vector)
        scores = [s for _, s in result]
        assert scores == sorted(scores, reverse=True)

    def test_rrf_score_formula(self):
        """验证 RRF 分数公式：1/(k + rank + 1)，k=60。"""
        k = 60
        bm25 = ["doc1"]
        vector = ["doc1"]
        result = rrf_merge(bm25, vector, k=k)
        expected_score = 2.0 / (k + 0 + 1)  # rank=0 in both
        actual_score = dict(result)["doc1"]
        assert abs(actual_score - expected_score) < 1e-9, (
            f"RRF 分数计算错误: 期望 {expected_score:.6f}, 实际 {actual_score:.6f}"
        )

    def test_rrf_different_k(self):
        """自定义 k 值影响分数。"""
        bm25 = ["doc1"]
        vector = []
        r_k60 = dict(rrf_merge(bm25, vector, k=60))
        r_k10 = dict(rrf_merge(bm25, vector, k=10))
        # k=10 时分数更大（分母更小）
        assert r_k10["doc1"] > r_k60["doc1"]

    def test_rrf_rank_matters(self):
        """排名靠前的文档分数更高。"""
        bm25 = ["first", "second", "third"]
        result = dict(rrf_merge(bm25, []))
        assert result["first"] > result["second"] > result["third"]

    def test_rrf_union_of_both_lists(self):
        """RRF 结果是两路的并集。"""
        bm25 = ["a", "b"]
        vector = ["c", "d"]
        result = rrf_merge(bm25, vector)
        ids = {r[0] for r in result}
        assert ids == {"a", "b", "c", "d"}


# ─────────────────────────── BM25 检索 ───────────────────────────

class TestBM25Search:

    def test_bm25_tokenize_chinese(self):
        """中文分词：按字切分。"""
        tokens = _tokenize("人工智能")
        assert "人" in tokens
        assert "工" in tokens

    def test_bm25_tokenize_english(self):
        """英文分词：按单词切分。"""
        tokens = _tokenize("hello world")
        assert "hello" in tokens
        assert "world" in tokens

    def test_bm25_returns_relevant_result(self):
        """BM25 对含关键词的文档打分更高。"""
        chunks = [
            RetrievedChunk("c1", "d1", "机器学习与深度学习", 0.0),
            RetrievedChunk("c2", "d2", "区块链技术去中心化", 0.0),
            RetrievedChunk("c3", "d3", "Python 编程语言基础", 0.0),
        ]
        result = bm25_search("机器学习", chunks, top_k=3)
        # c1 应排在最前（含关键词）
        assert result[0] == "c1"

    def test_bm25_top_k_limits_output(self):
        """top_k 限制 BM25 输出数量。"""
        chunks = [
            RetrievedChunk(f"c{i}", f"d{i}", f"文档内容{i}", 0.0)
            for i in range(10)
        ]
        result = bm25_search("文档", chunks, top_k=3)
        assert len(result) == 3

    def test_bm25_empty_chunks(self):
        """空 chunks 列表返回空结果。"""
        result = bm25_search("query", [], top_k=5)
        assert result == []


# ─────────────────────────── HybridRetriever 集成测试 ───────────────────────────

class TestHybridRetriever:

    def test_hybrid_retrieve_returns_results(self):
        """写入文档后混合检索能返回结果。"""
        hybrid, retriever, embedder = build_hybrid()
        ingest(retriever, embedder, "tA", "kb1", "doc1", "人工智能机器学习深度学习")

        results = hybrid.retrieve("tA", "kb1", "人工智能", top_k=5)
        assert len(results) >= 1
        # 只有一篇文档，必然是 doc1（不依赖排序稳定性）
        doc_ids = {r.doc_id for r in results}
        assert "doc1" in doc_ids

    def test_hybrid_retrieve_top_k_respected(self):
        """top_k 参数正确限制混合检索返回数量。"""
        hybrid, retriever, embedder = build_hybrid()
        for i in range(8):
            ingest(retriever, embedder, "tA", "kb2", f"doc{i}", f"文档内容{i}篇测试数据")

        results_3 = hybrid.retrieve("tA", "kb2", "文档", top_k=3)
        results_6 = hybrid.retrieve("tA", "kb2", "文档", top_k=6)

        assert len(results_3) <= 3
        assert len(results_6) <= 6
        assert len(results_3) == 3
        assert len(results_6) == 6

    def test_hybrid_retrieve_empty_kb_returns_empty(self):
        """空知识库混合检索返回空列表，不报错。"""
        hybrid, _, _ = build_hybrid()
        results = hybrid.retrieve("tA", "empty-kb", "查询", top_k=5)
        assert results == []

    def test_hybrid_result_scores_are_rrf_scores(self):
        """混合检索结果的 score 是 RRF 分数（>0）。"""
        hybrid, retriever, embedder = build_hybrid()
        ingest(retriever, embedder, "tA", "kb3", "doc1", "测试内容文档")

        results = hybrid.retrieve("tA", "kb3", "测试", top_k=5)
        assert len(results) >= 1
        for r in results:
            assert r.score > 0, "RRF 分数应 > 0"

    def test_hybrid_results_sorted_by_score_descending(self):
        """混合检索结果按 RRF 分数降序排列。"""
        hybrid, retriever, embedder = build_hybrid()
        for i in range(5):
            ingest(retriever, embedder, "tA", "kb4", f"doc{i}", f"文档{i}测试")

        results = hybrid.retrieve("tA", "kb4", "文档", top_k=5)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True), "结果应按分数降序"

    def test_hybrid_multi_tenant_isolation(self):
        """
        混合检索多租户隔离：
        租户A 的检索结果不包含租户B 的文档，反之亦然。
        """
        hybrid, retriever, embedder = build_hybrid()

        # 使用完全不同内容，避免向量相似导致混淆
        ingest(retriever, embedder, "tA", "kb5", "doc-a", "苹果橙子香蕉水果蔬菜" * 5)
        ingest(retriever, embedder, "tB", "kb5", "doc-b", "区块链以太坊比特币加密" * 5)

        results_a = hybrid.retrieve("tA", "kb5", "水果", top_k=10)
        results_b = hybrid.retrieve("tB", "kb5", "区块链", top_k=10)

        doc_ids_a = {r.doc_id for r in results_a}
        doc_ids_b = {r.doc_id for r in results_b}

        assert "doc-b" not in doc_ids_a, "租户A 检索结果不应包含租户B 的文档"
        assert "doc-a" not in doc_ids_b, "租户B 检索结果不应包含租户A 的文档"

    def test_hybrid_same_tenant_sees_own_docs(self):
        """同一租户在多次检索中始终只能看到自己的文档。"""
        hybrid, retriever, embedder = build_hybrid()

        ingest(retriever, embedder, "t1", "kb", "d1", "Python 编程语言")
        ingest(retriever, embedder, "t1", "kb", "d2", "机器学习算法")
        ingest(retriever, embedder, "t2", "kb", "d3", "其他租户数据")

        results = hybrid.retrieve("t1", "kb", "Python", top_k=10)
        doc_ids = {r.doc_id for r in results}

        assert "d3" not in doc_ids, "不应包含其他租户文档"
        # 自己的文档至少能检索到一部分
        assert len(results) >= 1

    def test_hybrid_retrieve_chunk_id_and_doc_id_correct(self):
        """混合检索结果中 chunk_id 和 doc_id 字段正确。"""
        hybrid, retriever, embedder = build_hybrid()
        ingest(retriever, embedder, "tA", "kb6", "my-doc", "测试文档内容信息")

        results = hybrid.retrieve("tA", "kb6", "测试", top_k=5)
        assert len(results) >= 1
        for r in results:
            assert r.chunk_id != ""
            assert r.doc_id == "my-doc"
            assert r.content != ""
