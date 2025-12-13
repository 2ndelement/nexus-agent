"""
memory-service 测试套件

使用 SQLite 内存数据库（不依赖外部 MySQL），异步测试。
Embedding 模型通过 mock 测试向量化路径，同时覆盖关键词降级路径。
"""
from __future__ import annotations

import math
import sys
import os
import pytest

# 将 memory-service 根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import event

from models import Base, Memory
from services.memory_service import (
    save_memory,
    retrieve_memories,
    delete_memory,
    _cosine_similarity,
    _keyword_score,
    _extract_keywords,
    _encode,
)

# ─── 测试数据库（SQLite 内存库）──────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    """提供异步 SQLite 内存数据库 session。"""
    try:
        engine = create_async_engine(TEST_DB_URL, echo=False)
    except Exception:
        pytest.skip("aiosqlite 未安装，跳过集成测试")
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


# ─── 单元测试：纯工具函数 ────────────────────────────────────────────────────

class TestCosineSimiliarity:
    def test_identical_vectors(self):
        a = [1.0, 0.0, 0.0]
        assert _cosine_similarity(a, a) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert _cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert _cosine_similarity(a, b) == pytest.approx(-1.0, abs=1e-6)

    def test_zero_vector(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_length_mismatch(self):
        assert _cosine_similarity([1.0], [1.0, 0.0]) == 0.0


class TestKeywordScore:
    def test_full_match(self):
        score = _keyword_score("人工智能 机器学习", "人工智能与机器学习", None)
        assert score > 0.5

    def test_no_match(self):
        score = _keyword_score("python java", "人工智能", None)
        assert score == 0.0

    def test_partial_match(self):
        score = _keyword_score("人工智能 数据库", "人工智能相关内容", None)
        assert 0.0 < score < 1.0

    def test_keywords_field_bonus(self):
        # keywords 字段也参与匹配
        score_with = _keyword_score("测试", "无关内容", "测试关键词")
        score_without = _keyword_score("测试", "无关内容", None)
        assert score_with > score_without

    def test_empty_query(self):
        assert _keyword_score("", "任意内容", None) == 0.0


class TestExtractKeywords:
    def test_english(self):
        kws = _extract_keywords("hello world foo")
        assert "hello" in kws
        assert "world" in kws

    def test_chinese(self):
        kws = _extract_keywords("人工智能，机器学习！")
        assert any(len(k) > 1 for k in kws)

    def test_filters_short_words(self):
        kws = _extract_keywords("a b cc ddd")
        assert "a" not in kws
        assert "b" not in kws
        assert "cc" in kws


# ─── 集成测试：save / retrieve / delete ──────────────────────────────────────

@pytest.mark.asyncio
async def test_save_memory_basic(db_session):
    """保存记忆片段，返回有效 ID"""
    mem = await save_memory(
        db_session,
        tenant_id=1,
        content="Python 是一门动态语言",
        user_id=100,
    )
    assert mem.id is not None
    assert mem.tenant_id == 1
    assert mem.content == "Python 是一门动态语言"
    assert mem.keywords is not None and len(mem.keywords) > 0


@pytest.mark.asyncio
async def test_save_memory_with_embedding(db_session):
    """使用 mock encoder 保存，验证 embedding 字段被写入"""
    mock_vec = [0.1, 0.2, 0.3]
    with patch("services.memory_service._encode", return_value=mock_vec), \
         patch("services.memory_service._encoder_loaded", True):
        mem = await save_memory(
            db_session,
            tenant_id=1,
            content="embedding 测试",
            user_id=101,
        )
    assert mem.embedding is not None
    parts = mem.embedding.split(",")
    assert len(parts) == 3
    assert abs(float(parts[0]) - 0.1) < 1e-5


@pytest.mark.asyncio
async def test_save_memory_fallback_no_embedding(db_session):
    """模型不可用时，embedding 字段为 None，但 keywords 正常写入"""
    with patch("services.memory_service._encode", return_value=None):
        mem = await save_memory(
            db_session,
            tenant_id=2,
            content="关键词降级测试",
            user_id=200,
        )
    assert mem.embedding is None
    assert mem.keywords is not None


@pytest.mark.asyncio
async def test_retrieve_with_keyword_fallback(db_session):
    """关键词模式检索：查询词在内容中有命中应排名靠前"""
    with patch("services.memory_service._encode", return_value=None):
        await save_memory(db_session, tenant_id=3, content="Python 编程语言很流行", user_id=300)
        await save_memory(db_session, tenant_id=3, content="完全不相关的内容", user_id=300)

        results = await retrieve_memories(
            db_session,
            tenant_id=3,
            query="Python 编程",
            user_id=300,
        )

    assert len(results) >= 1
    assert results[0]["content"] == "Python 编程语言很流行"


@pytest.mark.asyncio
async def test_retrieve_with_mock_embedding(db_session):
    """向量模式检索：相似度高的记忆排名靠前"""
    vec_a = [1.0, 0.0, 0.0]
    vec_b = [0.0, 1.0, 0.0]
    vec_query = [0.9, 0.1, 0.0]  # 与 vec_a 更相似

    call_count = [0]

    def mock_encode(text_str):
        call_count[0] += 1
        # 第1次：content_a，第2次：content_b，之后是 query
        if call_count[0] == 1:
            return vec_a
        elif call_count[0] == 2:
            return vec_b
        else:
            return vec_query

    with patch("services.memory_service._encode", side_effect=mock_encode), \
         patch("services.memory_service._encoder_loaded", True):
        await save_memory(db_session, tenant_id=4, content="内容A", user_id=400)
        await save_memory(db_session, tenant_id=4, content="内容B", user_id=400)
        results = await retrieve_memories(
            db_session,
            tenant_id=4,
            query="查询",
            user_id=400,
        )

    assert len(results) >= 2
    assert results[0]["content"] == "内容A"  # 与 query 更相似


@pytest.mark.asyncio
async def test_retrieve_multi_tenant_isolation(db_session):
    """多租户隔离：租户 A 的记忆不出现在租户 B 的查询结果中"""
    with patch("services.memory_service._encode", return_value=None):
        await save_memory(db_session, tenant_id=10, content="租户A的机密数据", user_id=1)
        await save_memory(db_session, tenant_id=20, content="租户B的机密数据", user_id=2)

        results_a = await retrieve_memories(
            db_session, tenant_id=10, query="机密数据"
        )
        results_b = await retrieve_memories(
            db_session, tenant_id=20, query="机密数据"
        )

    # 租户 A 只能看到自己的记忆
    assert all(r["tenant_id"] == 10 for r in results_a)
    assert all(r["tenant_id"] == 20 for r in results_b)
    # 各自能检索到自己的数据
    assert any("租户A" in r["content"] for r in results_a)
    assert any("租户B" in r["content"] for r in results_b)


@pytest.mark.asyncio
async def test_retrieve_empty_result(db_session):
    """不存在的租户查询返回空列表"""
    with patch("services.memory_service._encode", return_value=None):
        results = await retrieve_memories(
            db_session, tenant_id=9999, query="任意查询"
        )
    assert results == []


@pytest.mark.asyncio
async def test_retrieve_top_k_limit(db_session):
    """top_k 参数限制返回数量"""
    with patch("services.memory_service._encode", return_value=None):
        for i in range(5):
            await save_memory(
                db_session,
                tenant_id=50,
                content=f"记忆片段 {i} 关键词",
                user_id=500,
            )

        results = await retrieve_memories(
            db_session,
            tenant_id=50,
            query="关键词",
            user_id=500,
            top_k=3,
        )
    assert len(results) <= 3


@pytest.mark.asyncio
async def test_delete_memory_success(db_session):
    """删除属于自己租户的记忆 → 返回 True"""
    with patch("services.memory_service._encode", return_value=None):
        mem = await save_memory(db_session, tenant_id=60, content="待删除内容", user_id=600)

    deleted = await delete_memory(db_session, memory_id=mem.id, tenant_id=60)
    assert deleted is True


@pytest.mark.asyncio
async def test_delete_memory_wrong_tenant(db_session):
    """跨租户删除 → 返回 False（租户隔离）"""
    with patch("services.memory_service._encode", return_value=None):
        mem = await save_memory(db_session, tenant_id=70, content="租户70的记忆", user_id=700)

    # 租户 80 尝试删除租户 70 的记忆
    deleted = await delete_memory(db_session, memory_id=mem.id, tenant_id=80)
    assert deleted is False


@pytest.mark.asyncio
async def test_delete_memory_not_found(db_session):
    """删除不存在的 ID → 返回 False"""
    deleted = await delete_memory(db_session, memory_id=99999, tenant_id=1)
    assert deleted is False


@pytest.mark.asyncio
async def test_save_with_importance(db_session):
    """重要性字段正确写入"""
    with patch("services.memory_service._encode", return_value=None):
        mem = await save_memory(
            db_session,
            tenant_id=90,
            content="高重要性记忆",
            importance=9.5,
        )
    assert abs(mem.importance - 9.5) < 0.001


@pytest.mark.asyncio
async def test_retrieve_filter_by_agent_id(db_session):
    """agent_id 过滤正常工作"""
    with patch("services.memory_service._encode", return_value=None):
        await save_memory(db_session, tenant_id=100, content="Agent1 的记忆", agent_id=1)
        await save_memory(db_session, tenant_id=100, content="Agent2 的记忆", agent_id=2)

        results = await retrieve_memories(
            db_session, tenant_id=100, query="记忆", agent_id=1
        )

    assert all(r["agent_id"] == 1 for r in results)
    assert len(results) == 1
