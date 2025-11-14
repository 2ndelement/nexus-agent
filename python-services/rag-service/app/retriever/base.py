"""
app/retriever/base.py — BaseRetriever 抽象类

定义统一的 Retriever 接口，便于未来切换到 Milvus/ES。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetrievedChunk:
    """检索结果中的单个文档片段"""
    chunk_id: str
    doc_id: str
    content: str
    score: float                            # 归一化到 [0, 1]，越高越相关
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseRetriever(ABC):
    """
    向量检索抽象基类。

    多租户隔离由实现层保证：
    - Collection 命名：nexus_{tenant_id}_{kb_id}
    - 或 metadata filter: where={"tenant_id": tenant_id}
    """

    @abstractmethod
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
        """将文档 chunks 写入向量库。"""

    @abstractmethod
    def vector_search(
        self,
        tenant_id: str,
        kb_id: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """
        纯向量相似度检索。

        Returns:
            按 score 降序排列的 RetrievedChunk 列表。
        """

    @abstractmethod
    def get_all_chunks(
        self,
        tenant_id: str,
        kb_id: str,
    ) -> list[RetrievedChunk]:
        """获取指定租户+知识库的所有 chunks（供 BM25 使用）。"""

    @abstractmethod
    def delete_doc(
        self,
        tenant_id: str,
        kb_id: str,
        doc_id: str,
    ) -> None:
        """删除指定文档的所有 chunks。"""

    @abstractmethod
    def count(self, tenant_id: str, kb_id: str) -> int:
        """返回指定租户+知识库的 chunk 总数。"""
