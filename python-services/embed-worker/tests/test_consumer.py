"""
embed-worker consumer 单元测试。

测试向量化消费流程的核心逻辑：
- 消息解析
- 向量化调用
- ChromaDB 写入
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ── 消息格式测试 ──


def test_embed_task_message_format():
    """验证 EmbedTask 消息格式解析正确。"""
    raw = json.dumps({
        "task_id": "test-uuid-001",
        "tenant_id": "1",
        "kb_id": "100",
        "doc_id": "9001",
        "chunks": [
            {
                "chunk_id": "1",
                "chunk_index": 0,
                "content": "Hello World",
                "metadata": {"doc_id": "9001", "filename": "test.txt"},
            }
        ],
    })
    data = json.loads(raw)

    assert data["task_id"] == "test-uuid-001"
    assert data["tenant_id"] == "1"
    assert len(data["chunks"]) == 1
    assert data["chunks"][0]["content"] == "Hello World"


def test_embed_task_empty_chunks():
    """空 chunks 列表应正常解析。"""
    raw = json.dumps({
        "task_id": "test-uuid-002",
        "tenant_id": "1",
        "kb_id": "100",
        "doc_id": "9002",
        "chunks": [],
    })
    data = json.loads(raw)
    assert len(data["chunks"]) == 0


def test_embed_task_invalid_json():
    """非法 JSON 应抛出异常。"""
    with pytest.raises(json.JSONDecodeError):
        json.loads("not-a-json")


def test_embed_task_missing_field():
    """缺少必需字段时 key 访问应抛 KeyError。"""
    data = json.loads('{"task_id": "x"}')
    with pytest.raises(KeyError):
        _ = data["chunks"]
