"""
记忆服务核心业务逻辑。

职责：
1. 将记忆片段元数据存入 MySQL
2. 用 sentence-transformers 将文本向量化
3. 向量存储到 ChromaDB（替代 MySQL TEXT 字段）
4. 按相似度检索（ChromaDB 原生支持）+ 关键词降级
5. 全程多租户隔离：tenant_id 参与所有查询

ChromaDB 存储设计：
- Collection: nexus_memory_{tenant_id}
- Document: content 文本
- Metadata: user_id, agent_id, source, importance, memory_id
- Embedding: sentence-transformers 生成
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from models import Memory

logger = logging.getLogger(__name__)

# ─── ChromaDB 客户端（延迟初始化） ──────────────────────────────────────────

_chroma_client = None
_chroma_available: bool = False
_chroma_attempted: bool = False


def _get_chroma():
    """延迟初始化 ChromaDB 客户端。"""
    global _chroma_client, _chroma_available, _chroma_attempted
    if _chroma_attempted:
        return _chroma_client if _chroma_available else None
    _chroma_attempted = True

    try:
        import chromadb

        chroma_host = os.getenv("CHROMA_HOST", "127.0.0.1")
        chroma_port = int(os.getenv("CHROMA_PORT", "8000"))

        _chroma_client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
        # 测试连接
        _chroma_client.heartbeat()
        _chroma_available = True
        logger.info("ChromaDB 连接成功: %s:%s", chroma_host, chroma_port)
        return _chroma_client
    except Exception as exc:
        logger.warning("ChromaDB 连接失败，降级为关键词匹配模式: %s", exc)
        _chroma_available = False
        return None


def _get_collection(tenant_id: int):
    """获取租户专属 ChromaDB Collection。"""
    client = _get_chroma()
    if client is None:
        return None
    collection_name = f"nexus_memory_{tenant_id}"
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


# ─── Embedding 模型（延迟加载） ──────────────────────────────────────────────

_encoder = None
_encoder_loaded: bool = False
_encoder_attempted: bool = False

EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


def _load_encoder():
    global _encoder, _encoder_loaded, _encoder_attempted
    if _encoder_attempted:
        return
    _encoder_attempted = True
    try:
        from sentence_transformers import SentenceTransformer
        logger.info("正在加载 embedding 模型：%s", EMBEDDING_MODEL)
        _encoder = SentenceTransformer(EMBEDDING_MODEL)
        _encoder_loaded = True
        logger.info("Embedding 模型加载成功")
    except Exception as exc:
        logger.warning("Embedding 模型加载失败，将使用关键词匹配降级模式：%s", exc)
        _encoder_loaded = False


def _encode(text_str: str) -> Optional[list[float]]:
    """将文本编码为向量，失败返回 None。"""
    _load_encoder()
    if not _encoder_loaded or _encoder is None:
        return None
    try:
        vec = _encoder.encode(text_str, normalize_embeddings=True)
        return vec.tolist()
    except Exception as exc:
        logger.warning("向量化失败：%s", exc)
        return None


# ─── 关键词工具 ─────────────────────────────────────────────────────────────

def _extract_keywords(text_str: str) -> list[str]:
    """简单分词：以空白/标点分割，过滤长度<=1的词。"""
    words = re.split(r"[\s，。！？、；：,.!?;:\-\u3000]+", text_str)
    return [w.strip() for w in words if len(w.strip()) > 1]


def _keyword_score(query: str, content: str, keywords: Optional[str]) -> float:
    """关键词匹配得分：命中关键词数/query 关键词总数。"""
    q_keywords = set(_extract_keywords(query.lower()))
    if not q_keywords:
        return 0.0
    target = (content + " " + (keywords or "")).lower()
    hits = sum(1 for kw in q_keywords if kw in target)
    return hits / len(q_keywords)


# ─── 数据库操作 ─────────────────────────────────────────────────────────────

async def save_memory(
    session: AsyncSession,
    *,
    tenant_id: int,
    content: str,
    user_id: Optional[int] = None,
    agent_id: Optional[int] = None,
    source: Optional[str] = None,
    importance: float = 1.0,
) -> Memory:
    """
    保存记忆片段。

    1. 向量化 content
    2. 存储到 ChromaDB（向量 + 元数据）
    3. 存储到 MySQL（元数据，embedding 字段不再使用）
    """
    # 提取关键词
    keywords = ",".join(_extract_keywords(content))

    # MySQL 元数据（不再存 embedding TEXT）
    memory = Memory(
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id=agent_id,
        content=content,
        keywords=keywords,
        embedding=None,  # 不再存 MySQL TEXT
        source=source,
        importance=importance,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(memory)
    await session.commit()
    await session.refresh(memory)

    # ChromaDB 向量存储
    collection = _get_collection(tenant_id)
    if collection is not None:
        vec = _encode(content)
        metadata = {
            "memory_id": memory.id,
            "user_id": user_id or 0,
            "agent_id": agent_id or 0,
            "source": source or "",
            "importance": importance,
        }
        try:
            if vec is not None:
                collection.add(
                    ids=[str(memory.id)],
                    documents=[content],
                    embeddings=[vec],
                    metadatas=[metadata],
                )
            else:
                # 无向量时只存文本，让 ChromaDB 用内置模型
                collection.add(
                    ids=[str(memory.id)],
                    documents=[content],
                    metadatas=[metadata],
                )
            logger.debug("ChromaDB 记忆存储成功: id=%d", memory.id)
        except Exception as exc:
            logger.warning("ChromaDB 写入失败（不影响主流程）: %s", exc)

    return memory


async def retrieve_memories(
    session: AsyncSession,
    *,
    tenant_id: int,
    query: str,
    user_id: Optional[int] = None,
    agent_id: Optional[int] = None,
    top_k: int = 10,
    min_score: float = 0.0,
) -> list[dict]:
    """
    检索记忆：优先 ChromaDB 向量检索，降级时使用 MySQL + 关键词匹配。

    多租户隔离：ChromaDB 按 tenant_id 分 Collection。
    """
    # 尝试 ChromaDB 检索
    collection = _get_collection(tenant_id)
    if collection is not None:
        try:
            query_vec = _encode(query)

            # 构建 where 过滤条件
            where_filter = {}
            if user_id is not None:
                where_filter["user_id"] = user_id
            if agent_id is not None:
                where_filter["agent_id"] = agent_id

            if query_vec is not None:
                results = collection.query(
                    query_embeddings=[query_vec],
                    n_results=top_k,
                    where=where_filter if where_filter else None,
                    include=["documents", "metadatas", "distances"],
                )
            else:
                results = collection.query(
                    query_texts=[query],
                    n_results=top_k,
                    where=where_filter if where_filter else None,
                    include=["documents", "metadatas", "distances"],
                )

            if results and results["ids"] and results["ids"][0]:
                memory_ids = [int(mid) for mid in results["ids"][0]]
                documents = results["documents"][0] if results["documents"] else []
                metadatas = results["metadatas"][0] if results["metadatas"] else []
                distances = results["distances"][0] if results["distances"] else []

                # 从 MySQL 补充完整数据
                stmt = select(Memory).where(
                    Memory.id.in_(memory_ids),
                    Memory.tenant_id == tenant_id,
                )
                result = await session.execute(stmt)
                mem_map = {m.id: m for m in result.scalars().all()}

                output = []
                for i, mid in enumerate(memory_ids):
                    mem = mem_map.get(mid)
                    if mem is None:
                        continue
                    # ChromaDB 返回的是 distance（越小越相似），转换为 score
                    score = 1.0 - (distances[i] if i < len(distances) else 0.0)
                    weighted = score * (mem.importance or 1.0)
                    if weighted >= min_score:
                        output.append(_memory_to_dict(mem, weighted))

                output.sort(key=lambda x: x["score"], reverse=True)
                return output[:top_k]

        except Exception as exc:
            logger.warning("ChromaDB 检索失败，降级 MySQL: %s", exc)

    # 降级：MySQL 全量加载 + 关键词匹配
    stmt = select(Memory).where(Memory.tenant_id == tenant_id)
    if user_id is not None:
        stmt = stmt.where(Memory.user_id == user_id)
    if agent_id is not None:
        stmt = stmt.where(Memory.agent_id == agent_id)

    result = await session.execute(stmt)
    memories: list[Memory] = list(result.scalars().all())

    if not memories:
        return []

    scored: list[tuple[float, Memory]] = []
    for mem in memories:
        score = _keyword_score(query, mem.content, mem.keywords)
        weighted = score * (mem.importance or 1.0)
        if weighted >= min_score:
            scored.append((weighted, mem))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [_memory_to_dict(mem, score) for score, mem in scored[:top_k]]


async def delete_memory(
    session: AsyncSession,
    *,
    memory_id: int,
    tenant_id: int,
) -> bool:
    """
    删除记忆（MySQL + ChromaDB 双删）。
    只能删除属于该租户的记录。
    """
    # MySQL 删除
    stmt = (
        delete(Memory)
        .where(Memory.id == memory_id)
        .where(Memory.tenant_id == tenant_id)
    )
    result = await session.execute(stmt)
    await session.commit()
    deleted = result.rowcount > 0

    # ChromaDB 删除
    if deleted:
        collection = _get_collection(tenant_id)
        if collection is not None:
            try:
                collection.delete(ids=[str(memory_id)])
            except Exception as exc:
                logger.warning("ChromaDB 删除失败: %s", exc)

    return deleted


def _memory_to_dict(mem: Memory, score: float = 0.0) -> dict:
    return {
        "id": mem.id,
        "tenant_id": mem.tenant_id,
        "user_id": mem.user_id,
        "agent_id": mem.agent_id,
        "content": mem.content,
        "source": mem.source,
        "importance": mem.importance,
        "score": round(score, 4),
        "created_at": mem.created_at.isoformat() if mem.created_at else None,
        "updated_at": mem.updated_at.isoformat() if mem.updated_at else None,
    }
