"""
app/chroma_writer.py — ChromaDB 写入器

将向量化后的 chunk 写入 ChromaDB，支持多租户隔离（collection 命名隔离）。
"""
from __future__ import annotations
import logging
import re
from typing import Any

import chromadb

from app.config import settings
from app.schemas import ChunkPayload

logger = logging.getLogger(__name__)


def _safe_name(s: str) -> str:
    """清洗字符串为 ChromaDB 合法的 collection 名"""
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "-", s).strip("-._")
    return (cleaned[:60] or "x")[:512]


def _collection_name(tenant_id: str, kb_id: str) -> str:
    """生成 collection 名：nexus-{tenant}-{kb}"""
    return f"nexus-{_safe_name(tenant_id)}-{_safe_name(kb_id)}"


class ChromaWriter:
    """
    ChromaDB 写入器。
    
    支持两种模式：
    - http 模式：连接远程 ChromaDB 服务
    - persistent 模式：本地持久化存储
    - memory 模式：内存存储（测试用）
    """
    def __init__(self, mode: str | None = None):
        mode = mode or settings.chroma_mode
        if mode == "http":
            self._client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port
            )
        elif mode == "persistent":
            self._client = chromadb.PersistentClient(
                path=settings.chroma_persist_path
            )
        elif mode == "memory":
            self._client = chromadb.Client()
        else:
            raise ValueError(f"Unknown chroma mode: {mode}")
        logger.info("ChromaDB 连接模式: %s", mode)

    def _get_collection(self, tenant_id: str, kb_id: str):
        name = _collection_name(tenant_id, kb_id)
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )

    def write_chunks(
        self,
        tenant_id: str,
        kb_id: str,
        chunks: list[ChunkPayload],
        embeddings: list[list[float]],
    ) -> None:
        """批量写入 chunk + 向量到 ChromaDB"""
        if not chunks or not embeddings:
            return

        col = self._get_collection(tenant_id, kb_id)

        ids = [c.chunk_id for c in chunks]
        docs = [c.content for c in chunks]
        
        # 丰富 metadata
        metas = []
        for c in chunks:
            m = dict(c.metadata)
            m["tenant_id"] = tenant_id
            m["kb_id"] = kb_id
            m["doc_id"] = c.chunk_id.split("::")[0] if "::" in c.chunk_id else c.chunk_id
            # ChromaDB metadata 只支持 str/int/float/bool
            m = {k: v if isinstance(v, (str, int, float, bool)) else str(v) 
                 for k, v in m.items()}
            metas.append(m)

        col.add(
            ids=ids,
            embeddings=embeddings,
            documents=docs,
            metadatas=metas,
        )
        logger.info("写入 ChromaDB: tenant=%s, kb=%s, count=%d", tenant_id, kb_id, len(chunks))

    def delete_doc(self, tenant_id: str, kb_id: str, doc_id: str) -> None:
        """删除某个文档的所有 chunk"""
        col = self._get_collection(tenant_id, kb_id)
        # ChromaDB 不支持按 metadata 删除，只能 get 全部再 delete
        # 为简化，这里依赖外部保证 doc_id 与 chunk_id 的关联
        # 实际生产可用 where 过滤 (ChromaDB 0.4.16+ 支持 delete where)
        try:
            col.delete(where={"doc_id": doc_id})
        except Exception:
            logger.warning("delete_doc failed, doc_id=%s may not exist", doc_id)


# 全局单例
_writer: ChromaWriter | None = None


def get_writer() -> ChromaWriter:
    global _writer
    if _writer is None:
        _writer = ChromaWriter()
    return _writer
