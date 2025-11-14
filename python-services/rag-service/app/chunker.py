"""
app/chunker.py — 文档分片工具

策略：
- 按字符滑动窗口切分（chunk_size + chunk_overlap）
- 每个 chunk 携带 doc_id、chunk_index、原始 metadata
- 中文友好：按字符计数，不按词
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    """单个文档片段"""
    chunk_id: str          # 全局唯一 ID：sha256(doc_id + chunk_index)
    doc_id: str            # 来源文档 ID
    chunk_index: int       # 在文档内的序号（0-based）
    content: str           # 文本内容
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def make_chunk_id(cls, doc_id: str, chunk_index: int) -> str:
        raw = f"{doc_id}::{chunk_index}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


def chunk_document(
    doc_id: str,
    content: str,
    metadata: dict[str, Any] | None = None,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[Chunk]:
    """
    将文档切分为若干 Chunk。

    Args:
        doc_id: 文档 ID。
        content: 文档全文。
        metadata: 附加元数据（会被复制到每个 chunk）。
        chunk_size: 每个 chunk 的字符数上限。
        chunk_overlap: 相邻 chunk 的重叠字符数。

    Returns:
        Chunk 列表（至少包含1个）。
    """
    if metadata is None:
        metadata = {}

    # 内容为空时返回一个空chunk（保持接口一致）
    if not content.strip():
        return [
            Chunk(
                chunk_id=Chunk.make_chunk_id(doc_id, 0),
                doc_id=doc_id,
                chunk_index=0,
                content=content,
                metadata=dict(metadata),
            )
        ]

    chunks: list[Chunk] = []
    step = max(1, chunk_size - chunk_overlap)
    idx = 0
    chunk_index = 0

    while idx < len(content):
        end = min(idx + chunk_size, len(content))
        text = content[idx:end]

        chunks.append(
            Chunk(
                chunk_id=Chunk.make_chunk_id(doc_id, chunk_index),
                doc_id=doc_id,
                chunk_index=chunk_index,
                content=text,
                metadata=dict(metadata),
            )
        )
        chunk_index += 1

        if end == len(content):
            break
        idx += step

    return chunks
