"""
tests/conftest.py — 公共 fixtures

核心约束：
- ChromaDB 使用 EphemeralClient(allow_reset=True) 内存模式
- 每个 fixture 用后调用 client.reset() 清理，确保测试间隔离
- Embedding 使用 MockEmbedder（随机向量，不下载模型）
- FastAPI TestClient 替换 dependencies 为 Mock 版本

注意：chromadb.EphemeralClient() 所有实例共享同一底层存储进程，
因此必须在 teardown 时 reset，或在测试内使用唯一的 collection 名前缀。
"""
from __future__ import annotations

import uuid

import chromadb
import pytest
from chromadb.config import Settings
from fastapi.testclient import TestClient

from app.embedder import MockEmbedder, set_embedder, reset_embedder
from app.retriever.chroma_retriever import ChromaRetriever
from app.retriever.hybrid import HybridRetriever


def make_ephemeral_client() -> chromadb.ClientAPI:
    """创建允许 reset 的内存 ChromaDB client。"""
    return chromadb.EphemeralClient(settings=Settings(allow_reset=True))


# ─────────────────────────── 基础 Fixtures ───────────────────────────

@pytest.fixture
def mock_embedder():
    """返回 MockEmbedder（dim=64，不加载任何模型）。"""
    emb = MockEmbedder(dim=64)
    set_embedder(emb)
    yield emb
    reset_embedder()


@pytest.fixture
def chroma_client():
    """
    每个测试独立的 ChromaDB 内存 client。
    teardown 时调用 reset() 清理所有数据，确保测试间完全隔离。
    """
    client = make_ephemeral_client()
    yield client
    # teardown：清理所有 collections，避免污染下一个测试
    try:
        client.reset()
    except Exception:
        pass


@pytest.fixture
def chroma_retriever(chroma_client):
    """使用内存 ChromaDB 的 ChromaRetriever。"""
    return ChromaRetriever(client=chroma_client)


@pytest.fixture
def hybrid_retriever(chroma_retriever, mock_embedder):
    """使用内存 ChromaDB + MockEmbedder 的 HybridRetriever。"""
    return HybridRetriever(
        retriever=chroma_retriever,
        embedder=mock_embedder,
        rrf_k=60,
        candidate_factor=3,
    )


# ─────────────────────────── FastAPI TestClient ───────────────────────────

@pytest.fixture
def api_client(chroma_client, mock_embedder):
    """
    返回带 Mock 注入的 FastAPI TestClient。
    - ChromaDB → 内存 client（teardown 时 reset）
    - Embedder → MockEmbedder
    """
    from main import app
    import app.dependencies as deps

    deps.set_chroma_client(chroma_client)

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    deps.reset_chroma_client()
    reset_embedder()


@pytest.fixture
def tenant_a_headers():
    return {"X-Tenant-Id": "tenantA"}


@pytest.fixture
def tenant_b_headers():
    return {"X-Tenant-Id": "tenantB"}


# ─────────────────────────── 唯一 KB ID 工厂 ───────────────────────────

@pytest.fixture
def unique_kb():
    """返回一个每次调用都唯一的 kb_id 工厂，用于防止测试间 collection 冲突。"""
    def _make(prefix: str = "kb") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:8]}"
    return _make
