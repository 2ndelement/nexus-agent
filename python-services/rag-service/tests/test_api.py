"""
tests/test_api.py — API 层测试

覆盖场景：
1. POST /api/v1/knowledge/ingest → 200, 正确返回 chunks_count
2. POST /api/v1/knowledge/retrieve → 200, 返回检索结果
3. 写入后能检索到 → 端到端流程
4. 空消息 / 缺少 Header → 422
5. 多租户隔离：通过不同 X-Tenant-Id 验证
6. top_k 参数生效
7. DELETE 接口
8. /health 健康检查
"""
from __future__ import annotations

import chromadb
import pytest
from fastapi.testclient import TestClient

import app.dependencies as deps
from app.embedder import MockEmbedder, set_embedder, reset_embedder


# ─────────────────────────── Fixture ───────────────────────────

@pytest.fixture(autouse=False)
def api_client_fresh():
    """
    每个测试独立的内存 ChromaDB + MockEmbedder TestClient。
    使用 EphemeralClient(allow_reset=True)，teardown 时 reset 确保隔离。
    """
    from main import app
    from chromadb.config import Settings

    client_db = chromadb.EphemeralClient(settings=Settings(allow_reset=True))
    emb = MockEmbedder(dim=64)

    deps.set_chroma_client(client_db)
    set_embedder(emb)

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    deps.reset_chroma_client()
    reset_embedder()
    try:
        client_db.reset()
    except Exception:
        pass


# ─────────────────────────── 健康检查 ───────────────────────────

class TestHealth:
    def test_health_ok(self, api_client_fresh):
        r = api_client_fresh.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["service"] == "rag-service"


# ─────────────────────────── Ingest ───────────────────────────

class TestIngest:
    def test_ingest_success(self, api_client_fresh):
        """正常写入返回 200，chunks_count >= 1。"""
        r = api_client_fresh.post(
            "/api/v1/knowledge/ingest",
            json={
                "doc_id": "doc1",
                "content": "人工智能是计算机科学的一个分支",
                "knowledge_base_id": "kb1",
                "metadata": {"source": "test"},
            },
            headers={"X-Tenant-Id": "tenantA"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["doc_id"] == "doc1"
        assert data["chunks_count"] >= 1
        assert data["knowledge_base_id"] == "kb1"

    def test_ingest_missing_tenant_header_422(self, api_client_fresh):
        """缺少 X-Tenant-Id → 422。"""
        r = api_client_fresh.post(
            "/api/v1/knowledge/ingest",
            json={"doc_id": "d1", "content": "内容", "knowledge_base_id": "kb1"},
        )
        assert r.status_code == 422

    def test_ingest_empty_content_422(self, api_client_fresh):
        """空内容 → 422。"""
        r = api_client_fresh.post(
            "/api/v1/knowledge/ingest",
            json={"doc_id": "d1", "content": "", "knowledge_base_id": "kb1"},
            headers={"X-Tenant-Id": "tenantA"},
        )
        assert r.status_code == 422

    def test_ingest_empty_doc_id_422(self, api_client_fresh):
        """空 doc_id → 422。"""
        r = api_client_fresh.post(
            "/api/v1/knowledge/ingest",
            json={"doc_id": "", "content": "内容", "knowledge_base_id": "kb1"},
            headers={"X-Tenant-Id": "tenantA"},
        )
        assert r.status_code == 422

    def test_ingest_empty_kb_id_422(self, api_client_fresh):
        """空 knowledge_base_id → 422。"""
        r = api_client_fresh.post(
            "/api/v1/knowledge/ingest",
            json={"doc_id": "d1", "content": "内容", "knowledge_base_id": ""},
            headers={"X-Tenant-Id": "tenantA"},
        )
        assert r.status_code == 422

    def test_ingest_multiple_docs(self, api_client_fresh):
        """多次写入同一知识库，每次独立成功。"""
        for i in range(3):
            r = api_client_fresh.post(
                "/api/v1/knowledge/ingest",
                json={"doc_id": f"doc{i}", "content": f"文档内容{i}", "knowledge_base_id": "kb1"},
                headers={"X-Tenant-Id": "tenantA"},
            )
            assert r.status_code == 200


# ─────────────────────────── Retrieve ───────────────────────────

class TestRetrieve:
    def _ingest(self, client, tenant_id, doc_id, content, kb_id="kb1"):
        return client.post(
            "/api/v1/knowledge/ingest",
            json={"doc_id": doc_id, "content": content, "knowledge_base_id": kb_id},
            headers={"X-Tenant-Id": tenant_id},
        )

    def test_retrieve_after_ingest(self, api_client_fresh):
        """写入文档后能检索到结果。"""
        self._ingest(api_client_fresh, "tenantA", "doc1", "人工智能深度学习")

        r = api_client_fresh.post(
            "/api/v1/knowledge/retrieve",
            json={"query": "人工智能", "knowledge_base_id": "kb1", "top_k": 5},
            headers={"X-Tenant-Id": "tenantA"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert len(data["results"]) >= 1
        assert data["query"] == "人工智能"

    def test_retrieve_result_fields(self, api_client_fresh):
        """检索结果包含所有必要字段。"""
        self._ingest(api_client_fresh, "tenantA", "doc1", "测试文档内容字段验证")

        r = api_client_fresh.post(
            "/api/v1/knowledge/retrieve",
            json={"query": "测试", "knowledge_base_id": "kb1", "top_k": 5},
            headers={"X-Tenant-Id": "tenantA"},
        )
        data = r.json()
        result = data["results"][0]
        assert "chunk_id" in result
        assert "doc_id" in result
        assert "content" in result
        assert "score" in result
        assert "metadata" in result

    def test_retrieve_top_k(self, api_client_fresh):
        """top_k 参数正确限制返回数量。"""
        for i in range(6):
            self._ingest(api_client_fresh, "tA", f"doc{i}", f"文档{i}内容测试数据")

        r = api_client_fresh.post(
            "/api/v1/knowledge/retrieve",
            json={"query": "文档", "knowledge_base_id": "kb1", "top_k": 3},
            headers={"X-Tenant-Id": "tA"},
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["results"]) <= 3

    def test_retrieve_empty_kb_returns_empty(self, api_client_fresh):
        """空知识库检索返回 total=0。"""
        r = api_client_fresh.post(
            "/api/v1/knowledge/retrieve",
            json={"query": "查询", "knowledge_base_id": "empty-kb", "top_k": 5},
            headers={"X-Tenant-Id": "tenantA"},
        )
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_retrieve_missing_tenant_header_422(self, api_client_fresh):
        """缺少 X-Tenant-Id → 422。"""
        r = api_client_fresh.post(
            "/api/v1/knowledge/retrieve",
            json={"query": "test", "knowledge_base_id": "kb1", "top_k": 5},
        )
        assert r.status_code == 422

    def test_retrieve_empty_query_422(self, api_client_fresh):
        """空查询词 → 422。"""
        r = api_client_fresh.post(
            "/api/v1/knowledge/retrieve",
            json={"query": "", "knowledge_base_id": "kb1", "top_k": 5},
            headers={"X-Tenant-Id": "tenantA"},
        )
        assert r.status_code == 422

    def test_retrieve_top_k_too_large_422(self, api_client_fresh):
        """top_k > 50 → 422。"""
        r = api_client_fresh.post(
            "/api/v1/knowledge/retrieve",
            json={"query": "test", "knowledge_base_id": "kb1", "top_k": 100},
            headers={"X-Tenant-Id": "tenantA"},
        )
        assert r.status_code == 422

    def test_retrieve_top_k_zero_422(self, api_client_fresh):
        """top_k=0 → 422。"""
        r = api_client_fresh.post(
            "/api/v1/knowledge/retrieve",
            json={"query": "test", "knowledge_base_id": "kb1", "top_k": 0},
            headers={"X-Tenant-Id": "tenantA"},
        )
        assert r.status_code == 422


# ─────────────────────────── 多租户隔离（API 层） ───────────────────────────

class TestMultiTenantIsolationAPI:

    def test_tenant_isolation_via_api(self, api_client_fresh):
        """
        API 层多租户隔离：
        租户A 写入文档后，租户B 用同 kb_id 检索，不应返回租户A 的文档。
        """
        # 租户A 写入
        api_client_fresh.post(
            "/api/v1/knowledge/ingest",
            json={"doc_id": "doc-a", "content": "租户A的专属内容ABC", "knowledge_base_id": "shared-kb"},
            headers={"X-Tenant-Id": "tenantA"},
        )

        # 租户B 检索
        r = api_client_fresh.post(
            "/api/v1/knowledge/retrieve",
            json={"query": "租户A", "knowledge_base_id": "shared-kb", "top_k": 10},
            headers={"X-Tenant-Id": "tenantB"},
        )
        assert r.status_code == 200
        data = r.json()
        # 租户B 的知识库为空，无结果
        assert data["total"] == 0, (
            f"租户B 不应检索到租户A 的文档，实际返回: {data}"
        )

    def test_each_tenant_sees_own_docs(self, api_client_fresh):
        """各租户只能看到自己的文档。"""
        # 写入
        api_client_fresh.post(
            "/api/v1/knowledge/ingest",
            json={"doc_id": "da", "content": "A租户内容", "knowledge_base_id": "kb"},
            headers={"X-Tenant-Id": "tA"},
        )
        api_client_fresh.post(
            "/api/v1/knowledge/ingest",
            json={"doc_id": "db", "content": "B租户内容", "knowledge_base_id": "kb"},
            headers={"X-Tenant-Id": "tB"},
        )

        # 检索
        r_a = api_client_fresh.post(
            "/api/v1/knowledge/retrieve",
            json={"query": "内容", "knowledge_base_id": "kb", "top_k": 10},
            headers={"X-Tenant-Id": "tA"},
        )
        r_b = api_client_fresh.post(
            "/api/v1/knowledge/retrieve",
            json={"query": "内容", "knowledge_base_id": "kb", "top_k": 10},
            headers={"X-Tenant-Id": "tB"},
        )

        doc_ids_a = {item["doc_id"] for item in r_a.json()["results"]}
        doc_ids_b = {item["doc_id"] for item in r_b.json()["results"]}

        assert "db" not in doc_ids_a, "租户A 不应看到租户B 的文档"
        assert "da" not in doc_ids_b, "租户B 不应看到租户A 的文档"


# ─────────────────────────── Delete ───────────────────────────

class TestDelete:
    def test_delete_doc(self, api_client_fresh):
        """写入后删除，再检索返回空。"""
        api_client_fresh.post(
            "/api/v1/knowledge/ingest",
            json={"doc_id": "doc-del", "content": "待删除文档内容", "knowledge_base_id": "kb1"},
            headers={"X-Tenant-Id": "tA"},
        )

        r_del = api_client_fresh.post(
            "/api/v1/knowledge/delete",
            json={"doc_id": "doc-del", "knowledge_base_id": "kb1"},
            headers={"X-Tenant-Id": "tA"},
        )
        assert r_del.status_code == 200
        assert r_del.json()["doc_id"] == "doc-del"

        r_count = api_client_fresh.get(
            "/api/v1/knowledge/count",
            params={"knowledge_base_id": "kb1"},
            headers={"X-Tenant-Id": "tA"},
        )
        assert r_count.json()["count"] == 0
