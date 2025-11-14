"""
tests/test_retriever.py — ChromaRetriever + 多租户隔离测试

覆盖场景：
1. 写入文档 → 向量检索能返回结果
2. 多租户隔离：租户A 的文档不出现在租户B 的检索结果里
3. get_all_chunks 正确返回全量数据
4. delete_doc 删除后不再返回
5. count 准确反映入库数量
6. top_k 参数生效
7. collection 命名格式验证
"""
from __future__ import annotations

import chromadb
import numpy as np
import pytest

from app.chunker import chunk_document
from app.retriever.chroma_retriever import ChromaRetriever, _collection_name
from app.retriever.base import RetrievedChunk


# ─────────────────────────── Helper ───────────────────────────

def add_doc(
    retriever: ChromaRetriever,
    tenant_id: str,
    kb_id: str,
    doc_id: str,
    content: str,
    dim: int = 64,
):
    """辅助函数：将文档分片并以随机向量写入 ChromaRetriever。"""
    chunks = chunk_document(doc_id=doc_id, content=content)
    rng = np.random.RandomState(abs(hash(content)) % (2**31))
    embeddings = [rng.randn(dim).astype(float).tolist() for _ in chunks]
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


# ─────────────────────────── 基础写入与检索 ───────────────────────────

class TestChromaRetrieverBasic:

    def test_add_and_vector_search_returns_result(self, chroma_retriever, mock_embedder):
        """写入文档后向量检索能返回结果。"""
        add_doc(chroma_retriever, "t1", "kb1", "doc1", "人工智能与机器学习")

        query_emb = mock_embedder.embed_query("人工智能")
        results = chroma_retriever.vector_search("t1", "kb1", query_emb, top_k=5)

        assert len(results) >= 1
        assert results[0].chunk_id != ""
        assert results[0].doc_id == "doc1"
        assert "人工智能" in results[0].content or len(results[0].content) > 0

    def test_vector_search_empty_collection_returns_empty(self, chroma_retriever, mock_embedder):
        """空知识库检索返回空列表，不报错。"""
        query_emb = mock_embedder.embed_query("test")
        results = chroma_retriever.vector_search("t1", "empty-kb", query_emb, top_k=5)
        assert results == []

    def test_get_all_chunks_returns_correct_count(self, chroma_retriever):
        """get_all_chunks 返回全量 chunks。"""
        # 写入3条短文档（每条1个chunk）
        for i in range(3):
            add_doc(chroma_retriever, "t1", "kb2", f"doc{i}", f"文档内容{i}" * 10)

        all_chunks = chroma_retriever.get_all_chunks("t1", "kb2")
        assert len(all_chunks) == 3

    def test_count_reflects_actual_chunks(self, chroma_retriever):
        """count() 准确反映写入的 chunk 数量。"""
        assert chroma_retriever.count("t1", "kb3") == 0

        add_doc(chroma_retriever, "t1", "kb3", "doc1", "短文档A")
        add_doc(chroma_retriever, "t1", "kb3", "doc2", "短文档B")

        assert chroma_retriever.count("t1", "kb3") == 2

    def test_delete_doc_removes_chunks(self, chroma_retriever):
        """delete_doc 后该文档的 chunks 不再出现。"""
        add_doc(chroma_retriever, "t1", "kb4", "doc-keep", "保留的文档内容")
        add_doc(chroma_retriever, "t1", "kb4", "doc-del", "要删除的文档内容")

        assert chroma_retriever.count("t1", "kb4") == 2

        chroma_retriever.delete_doc("t1", "kb4", "doc-del")

        assert chroma_retriever.count("t1", "kb4") == 1
        remaining = chroma_retriever.get_all_chunks("t1", "kb4")
        assert all(c.doc_id != "doc-del" for c in remaining)
        assert any(c.doc_id == "doc-keep" for c in remaining)

    def test_top_k_limits_results(self, chroma_retriever, mock_embedder):
        """top_k 参数正确限制返回数量。"""
        for i in range(10):
            add_doc(chroma_retriever, "t1", "kb5", f"doc{i}", f"内容文档第{i}篇")

        query_emb = mock_embedder.embed_query("内容")
        results_3 = chroma_retriever.vector_search("t1", "kb5", query_emb, top_k=3)
        results_7 = chroma_retriever.vector_search("t1", "kb5", query_emb, top_k=7)

        assert len(results_3) == 3
        assert len(results_7) == 7

    def test_vector_search_score_in_range(self, chroma_retriever, mock_embedder):
        """向量检索的 score 应在 [0, 1] 范围内。"""
        add_doc(chroma_retriever, "t1", "kb6", "doc1", "测试文档内容")
        query_emb = mock_embedder.embed_query("测试")
        results = chroma_retriever.vector_search("t1", "kb6", query_emb, top_k=5)
        for r in results:
            assert 0.0 <= r.score <= 1.0, f"score 超范围: {r.score}"


# ─────────────────────────── 多租户隔离 ───────────────────────────

class TestMultiTenantIsolation:
    """
    多租户隔离测试。

    注意：chromadb.EphemeralClient() 所有实例共享同一底层存储，
    因此各测试方法使用 chroma_retriever fixture（会在 teardown reset）
    或使用 unique_kb fixture 生成唯一 kb_id 确保 collection 名不冲突。
    """

    def test_tenant_data_isolated_in_search(self, chroma_retriever, mock_embedder, unique_kb):
        """
        核心隔离测试：租户A 的文档不出现在租户B 的检索结果里。

        同一个 ChromaRetriever 实例（同一底层 ChromaDB），
        不同租户通过 collection 命名隔离（nexus-tenantA-kb vs nexus-tenantB-kb）。
        """
        kb = unique_kb("isolation")

        # 租户A 写入文档
        add_doc(chroma_retriever, "tenantA", kb, "doc-a1", "人工智能深度学习神经网络")
        add_doc(chroma_retriever, "tenantA", kb, "doc-a2", "自然语言处理文本分类")

        # 租户B 写入文档
        add_doc(chroma_retriever, "tenantB", kb, "doc-b1", "区块链去中心化分布式")
        add_doc(chroma_retriever, "tenantB", kb, "doc-b2", "量子计算量子纠缠")

        # 租户A 检索（top_k=10，应只返回2条）
        q_emb = mock_embedder.embed_query("人工智能")
        results_a = chroma_retriever.vector_search("tenantA", kb, q_emb, top_k=10)
        doc_ids_a = {r.doc_id for r in results_a}

        # 租户B 检索
        results_b = chroma_retriever.vector_search("tenantB", kb, q_emb, top_k=10)
        doc_ids_b = {r.doc_id for r in results_b}

        # 严格隔离：租户A 结果中无租户B 文档，反之亦然
        assert "doc-b1" not in doc_ids_a, "租户A 结果不应包含租户B 的文档 doc-b1"
        assert "doc-b2" not in doc_ids_a, "租户A 结果不应包含租户B 的文档 doc-b2"
        assert "doc-a1" not in doc_ids_b, "租户B 结果不应包含租户A 的文档 doc-a1"
        assert "doc-a2" not in doc_ids_b, "租户B 结果不应包含租户A 的文档 doc-a2"

        # 各自能检索到自己的文档（且只有自己的）
        assert len(results_a) == 2
        assert len(results_b) == 2

    def test_same_kb_id_different_tenants_isolated(self, chroma_retriever, mock_embedder, unique_kb):
        """
        同 kb_id，不同 tenant_id → 完全隔离（collection 名不同）。
        """
        same_kb = unique_kb("shared")
        add_doc(chroma_retriever, "tenant-X", same_kb, "doc-x", "X 租户专属内容 ABC")
        add_doc(chroma_retriever, "tenant-Y", same_kb, "doc-y", "Y 租户专属内容 DEF")

        chunks_x = chroma_retriever.get_all_chunks("tenant-X", same_kb)
        chunks_y = chroma_retriever.get_all_chunks("tenant-Y", same_kb)

        doc_ids_x = {c.doc_id for c in chunks_x}
        doc_ids_y = {c.doc_id for c in chunks_y}

        assert "doc-y" not in doc_ids_x
        assert "doc-x" not in doc_ids_y
        assert "doc-x" in doc_ids_x
        assert "doc-y" in doc_ids_y

    def test_get_all_chunks_isolated_per_tenant(self, chroma_retriever, mock_embedder, unique_kb):
        """get_all_chunks 只返回指定租户的数据。"""
        kb = unique_kb("chunks")
        add_doc(chroma_retriever, "tA", kb, "docA1", "内容A")
        add_doc(chroma_retriever, "tA", kb, "docA2", "内容AA")
        add_doc(chroma_retriever, "tB", kb, "docB1", "内容B")

        chunks_a = chroma_retriever.get_all_chunks("tA", kb)
        chunks_b = chroma_retriever.get_all_chunks("tB", kb)

        assert len(chunks_a) == 2
        assert len(chunks_b) == 1
        assert all(c.doc_id.startswith("docA") for c in chunks_a)
        assert all(c.doc_id.startswith("docB") for c in chunks_b)

    def test_delete_in_one_tenant_does_not_affect_another(self, chroma_retriever, mock_embedder, unique_kb):
        """在租户A 删除文档，不影响租户B 的数据。"""
        kb = unique_kb("del")
        add_doc(chroma_retriever, "tA", kb, "shared-doc-id", "A 的内容")
        add_doc(chroma_retriever, "tB", kb, "shared-doc-id", "B 的内容")

        chroma_retriever.delete_doc("tA", kb, "shared-doc-id")

        assert chroma_retriever.count("tA", kb) == 0
        assert chroma_retriever.count("tB", kb) == 1  # 租户B 不受影响


# ─────────────────────────── Collection 命名 ───────────────────────────

class TestCollectionNaming:

    def test_collection_name_format(self):
        """collection 名称必须以 nexus- 开头，包含 tenant 和 kb 信息。"""
        name = _collection_name("tenantA", "kb1")
        assert name.startswith("nexus-")
        assert "tenantA" in name or "tenanta" in name.lower()

    def test_different_tenants_different_collections(self):
        """不同租户生成不同 collection 名称。"""
        name_a = _collection_name("tenantA", "kb1")
        name_b = _collection_name("tenantB", "kb1")
        assert name_a != name_b

    def test_different_kbs_different_collections(self):
        """同一租户不同知识库生成不同 collection 名称。"""
        name1 = _collection_name("tenant1", "kb1")
        name2 = _collection_name("tenant1", "kb2")
        assert name1 != name2

    def test_collection_name_valid_chars(self):
        """collection 名称只包含 ChromaDB 允许的字符。"""
        import re
        for tenant, kb in [("tenant-A", "kb-001"), ("org.xyz", "base_1"), ("t1", "k1")]:
            name = _collection_name(tenant, kb)
            assert re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]$', name), (
                f"collection name '{name}' 含非法字符"
            )
            assert 3 <= len(name) <= 512
