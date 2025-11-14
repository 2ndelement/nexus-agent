"""
app/dependencies.py — FastAPI 依赖注入

提供 ChromaDB client、Embedder、HybridRetriever 的单例管理。
测试时可通过 override_dependencies() 替换为 Mock 版本。
"""
from __future__ import annotations

import chromadb

from app.config import settings
from app.embedder import BaseEmbedder, get_embedder
from app.retriever.chroma_retriever import ChromaRetriever
from app.retriever.hybrid import HybridRetriever

# ─────────────────────────── ChromaDB Client 单例 ───────────────────────────

_chroma_client: chromadb.ClientAPI | None = None


def get_chroma_client() -> chromadb.ClientAPI:
    global _chroma_client
    if _chroma_client is None:
        if settings.chroma_mode == "persistent":
            _chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        else:
            _chroma_client = chromadb.Client()
    return _chroma_client


def set_chroma_client(client: chromadb.ClientAPI) -> None:
    """测试注入：替换 ChromaDB client（内存模式）。"""
    global _chroma_client
    _chroma_client = client


def reset_chroma_client() -> None:
    global _chroma_client
    _chroma_client = None


# ─────────────────────────── FastAPI Depends ───────────────────────────

def get_retriever() -> ChromaRetriever:
    """FastAPI Depends：获取 ChromaRetriever 实例。"""
    return ChromaRetriever(client=get_chroma_client())


def get_hybrid_retriever() -> HybridRetriever:
    """FastAPI Depends：获取 HybridRetriever 实例。"""
    return HybridRetriever(
        retriever=get_retriever(),
        embedder=get_embedder(),
        rrf_k=settings.rrf_k,
        candidate_factor=settings.bm25_top_k_factor,
    )
