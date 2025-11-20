"""
app/core/embedder.py — Embedder（从 app.embedder re-export）

保持 app/core/embedder.py 路径约定，实现在 app/embedder.py。
"""
from app.embedder import (  # noqa: F401
    BaseEmbedder,
    MockEmbedder,
    SentenceTransformerEmbedder,
    get_embedder,
    set_embedder,
    reset_embedder,
)

__all__ = [
    "BaseEmbedder",
    "MockEmbedder",
    "SentenceTransformerEmbedder",
    "get_embedder",
    "set_embedder",
    "reset_embedder",
]
