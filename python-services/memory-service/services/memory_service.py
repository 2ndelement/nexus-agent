"""
记忆服务核心业务逻辑。

职责：
1. 将记忆片段存入 MySQL
2. 用 sentence-transformers 将文本向量化（失败时降级关键词匹配）
3. 按相似度检索（余弦相似度 / 关键词匹配）
4. 全程多租户隔离：tenant_id 参与所有查询
"""
from __future__ import annotations

import logging
import math
import re
from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from models import Memory

logger = logging.getLogger(__name__)

# ─── 向量模型（懒加载，加载失败降级关键词模式）─────────────────────────────────

_encoder = None
_encoder_loaded: bool = False   # True = 加载成功, False = 加载失败/未尝试
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


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算余弦相似度（向量已归一化则等于点积）。"""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _embedding_to_str(vec: list[float]) -> str:
    return ",".join(f"{v:.6f}" for v in vec)


def _str_to_embedding(s: str) -> Optional[list[float]]:
    if not s:
        return None
    try:
        return [float(x) for x in s.split(",")]
    except ValueError:
        return None


def _extract_keywords(text_str: str) -> list[str]:
    """简单分词：以空白/标点分割，过滤长度<=1的词。"""
    words = re.split(r"[\s，。！？、；：,.!?;:\-\u3000]+", text_str)
    return [w.strip() for w in words if len(w.strip()) > 1]


def _keyword_score(query: str, content: str, keywords: Optional[str]) -> float:
    """关键词匹配得分：命中关键词数/query 关键词总数。"""
    q_keywords = set(_extract_keywords(query.lower()))
    if not q_keywords:
        return 0.0
    # 在 content 和 keywords 字段中查找命中
    target = (content + " " + (keywords or "")).lower()
    hits = sum(1 for kw in q_keywords if kw in target)
    return hits / len(q_keywords)


# ─── 数据库操作 ──────────────────────────────────────────────────────────────

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
    保存记忆片段到 MySQL。
    同时生成 embedding（若可用）和关键词索引。
    """
    # 提取关键词
    keywords = ",".join(_extract_keywords(content))

    # 向量化
    vec = _encode(content)
    embedding_str = _embedding_to_str(vec) if vec is not None else None

    memory = Memory(
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id=agent_id,
        content=content,
        keywords=keywords,
        embedding=embedding_str,
        source=source,
        importance=importance,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(memory)
    await session.commit()
    await session.refresh(memory)
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
    检索记忆：向量相似度优先，降级时使用关键词匹配。

    多租户隔离：所有查询均携带 tenant_id 过滤。
    """
    # 拉取候选记录
    stmt = select(Memory).where(Memory.tenant_id == tenant_id)
    if user_id is not None:
        stmt = stmt.where(Memory.user_id == user_id)
    if agent_id is not None:
        stmt = stmt.where(Memory.agent_id == agent_id)

    result = await session.execute(stmt)
    memories: list[Memory] = list(result.scalars().all())

    if not memories:
        return []

    # 向量化 query
    query_vec = _encode(query)
    use_embedding = query_vec is not None

    scored: list[tuple[float, Memory]] = []
    for mem in memories:
        if use_embedding and mem.embedding:
            mem_vec = _str_to_embedding(mem.embedding)
            if mem_vec is not None:
                score = _cosine_similarity(query_vec, mem_vec)
            else:
                score = _keyword_score(query, mem.content, mem.keywords)
        else:
            score = _keyword_score(query, mem.content, mem.keywords)

        # 权重融合：得分 × 重要性
        weighted = score * (mem.importance or 1.0)
        if weighted >= min_score:
            scored.append((weighted, mem))

    # 按得分降序，取 top_k
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    return [_memory_to_dict(mem, score) for score, mem in top]


async def delete_memory(
    session: AsyncSession,
    *,
    memory_id: int,
    tenant_id: int,
) -> bool:
    """
    删除记忆（只能删除属于该租户的记录）。
    返回 True 表示成功删除，False 表示记录不存在或不属于该租户。
    """
    stmt = (
        delete(Memory)
        .where(Memory.id == memory_id)
        .where(Memory.tenant_id == tenant_id)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0


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
