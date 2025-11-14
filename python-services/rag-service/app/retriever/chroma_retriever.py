"""
app/retriever/chroma_retriever.py — ChromaDB 实现

多租户隔离策略：Collection 命名隔离
    collection_name = f"nexus_{tenant_id}_{kb_id}"

ChromaDB 1.5.x collection 名称规则：
    3-512 chars, [a-zA-Z0-9._-], 首尾必须是 [a-zA-Z0-9]
    因此 tenant_id / kb_id 中若含特殊字符需清洗。
"""
from __future__ import annotations

import logging
import re
from typing import Any

import chromadb

from app.retriever.base import BaseRetriever, RetrievedChunk

logger = logging.getLogger(__name__)

# ChromaDB 距离 → 相似度分数（cosine 距离：distance ∈ [0, 2]）
_DISTANCE_TO_SCORE = lambda d: max(0.0, 1.0 - d / 2.0)


def _safe_name_part(s: str) -> str:
    """
    将任意字符串清洗为 ChromaDB collection 名称合法部分。
    替换非 [a-zA-Z0-9._-] 为 '-'，截断至 60 字符。
    """
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "-", s)
    # 首尾必须是字母或数字
    cleaned = cleaned.strip("-._")
    if not cleaned:
        cleaned = "x"
    return cleaned[:60]


def _collection_name(tenant_id: str, kb_id: str) -> str:
    """
    生成 ChromaDB collection 名称。

    格式：nexus_{safe_tenant_id}_{safe_kb_id}
    保证全局隔离：不同租户即使 kb_id 相同也映射到不同 collection。
    """
    t = _safe_name_part(tenant_id)
    k = _safe_name_part(kb_id)
    name = f"nexus-{t}-{k}"
    # ChromaDB 要求最小长度 3
    if len(name) < 3:
        name = name + "xxx"
    return name[:512]


class ChromaRetriever(BaseRetriever):
    """
    基于 ChromaDB 的向量检索实现。

    Args:
        client: chromadb.Client 实例。
                内存模式（测试）：chromadb.Client()
                持久化模式（生产）：chromadb.PersistentClient(path=...)
    """

    def __init__(self, client: chromadb.ClientAPI):
        self._client = client

    # ─────────────────────── 私有工具 ───────────────────────

    def _get_or_create_collection(
        self,
        tenant_id: str,
        kb_id: str,
    ) -> chromadb.Collection:
        name = _collection_name(tenant_id, kb_id)
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    # ─────────────────────── 公共接口 ───────────────────────

    def add_chunks(
        self,
        tenant_id: str,
        kb_id: str,
        chunk_ids: list[str],
        doc_ids: list[str],
        contents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        if not chunk_ids:
            return

        col = self._get_or_create_collection(tenant_id, kb_id)

        # 为每个 chunk 的 metadata 注入 tenant_id 和 doc_id（便于过滤/删除）
        enriched_meta = []
        for i, meta in enumerate(metadatas):
            m = dict(meta)
            m["tenant_id"] = tenant_id
            m["kb_id"] = kb_id
            m["doc_id"] = doc_ids[i]
            # ChromaDB metadata 只支持 str/int/float/bool，将其余类型转 str
            cleaned = {
                k: v if isinstance(v, (str, int, float, bool)) else str(v)
                for k, v in m.items()
            }
            enriched_meta.append(cleaned)

        col.add(
            ids=chunk_ids,
            embeddings=embeddings,
            documents=contents,
            metadatas=enriched_meta,
        )
        logger.debug(
            "add_chunks: tenant=%s, kb=%s, count=%d",
            tenant_id, kb_id, len(chunk_ids),
        )

    def vector_search(
        self,
        tenant_id: str,
        kb_id: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        col = self._get_or_create_collection(tenant_id, kb_id)

        n = col.count()
        if n == 0:
            return []

        actual_k = min(top_k, n)
        result = col.query(
            query_embeddings=[query_embedding],
            n_results=actual_k,
            include=["documents", "metadatas", "distances"],
        )

        chunks: list[RetrievedChunk] = []
        ids = result["ids"][0]
        docs = result["documents"][0]
        metas = result["metadatas"][0]
        dists = result["distances"][0]

        for cid, doc, meta, dist in zip(ids, docs, metas, dists):
            chunks.append(
                RetrievedChunk(
                    chunk_id=cid,
                    doc_id=meta.get("doc_id", ""),
                    content=doc,
                    score=_DISTANCE_TO_SCORE(dist),
                    metadata={k: v for k, v in meta.items()
                               if k not in ("tenant_id", "kb_id", "doc_id")},
                )
            )

        return chunks

    def get_all_chunks(
        self,
        tenant_id: str,
        kb_id: str,
    ) -> list[RetrievedChunk]:
        col = self._get_or_create_collection(tenant_id, kb_id)
        n = col.count()
        if n == 0:
            return []

        result = col.get(
            include=["documents", "metadatas"],
            limit=n,
        )

        chunks: list[RetrievedChunk] = []
        for cid, doc, meta in zip(
            result["ids"], result["documents"], result["metadatas"]
        ):
            chunks.append(
                RetrievedChunk(
                    chunk_id=cid,
                    doc_id=meta.get("doc_id", ""),
                    content=doc,
                    score=0.0,
                    metadata={k: v for k, v in meta.items()
                               if k not in ("tenant_id", "kb_id", "doc_id")},
                )
            )
        return chunks

    def delete_doc(
        self,
        tenant_id: str,
        kb_id: str,
        doc_id: str,
    ) -> None:
        col = self._get_or_create_collection(tenant_id, kb_id)
        col.delete(where={"doc_id": doc_id})
        logger.info("delete_doc: tenant=%s, kb=%s, doc=%s", tenant_id, kb_id, doc_id)

    def count(self, tenant_id: str, kb_id: str) -> int:
        col = self._get_or_create_collection(tenant_id, kb_id)
        return col.count()
