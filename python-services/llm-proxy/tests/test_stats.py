"""
tests/test_stats.py — Token 统计接口测试
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.token_stats import token_stats


class TestStatsEndpoint:
    def test_initial_stats_zero(self, client):
        """初始状态下统计应为全零。"""
        resp = client.get("/v1/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requests"] == 0
        assert data["total_tokens"] == 0
        assert data["by_model"] == {}

    @pytest.mark.asyncio
    async def test_stats_after_record(self, client):
        """记录一次后统计应正确累加。"""
        await token_stats.record("MiniMax-M2.5-highspeed", prompt_tokens=10, completion_tokens=5)

        resp = client.get("/v1/stats")
        data = resp.json()

        assert data["total_requests"] == 1
        assert data["total_tokens"] == 15
        assert "MiniMax-M2.5-highspeed" in data["by_model"]
        model_stat = data["by_model"]["MiniMax-M2.5-highspeed"]
        assert model_stat["requests"] == 1
        assert model_stat["prompt_tokens"] == 10
        assert model_stat["completion_tokens"] == 5
        assert model_stat["total_tokens"] == 15

    @pytest.mark.asyncio
    async def test_stats_multi_model(self, client):
        """多个 model 统计应分别累计。"""
        await token_stats.record("model-a", prompt_tokens=20, completion_tokens=10)
        await token_stats.record("model-b", prompt_tokens=5, completion_tokens=3)
        await token_stats.record("model-a", prompt_tokens=8, completion_tokens=4)

        resp = client.get("/v1/stats")
        data = resp.json()

        assert data["total_requests"] == 3
        assert data["total_tokens"] == 50  # 30 + 8 + 12

        assert data["by_model"]["model-a"]["requests"] == 2
        assert data["by_model"]["model-a"]["total_tokens"] == 42  # 30 + 12
        assert data["by_model"]["model-b"]["requests"] == 1
        assert data["by_model"]["model-b"]["total_tokens"] == 8

    def test_reset_stats(self, client):
        """DELETE /v1/stats 应重置统计。"""
        token_stats._total_requests = 5
        token_stats._total_tokens = 100

        resp = client.delete("/v1/stats")
        assert resp.status_code == 200

        resp2 = client.get("/v1/stats")
        data = resp2.json()
        assert data["total_requests"] == 0
        assert data["total_tokens"] == 0


class TestTokenStatsUnit:
    @pytest.mark.asyncio
    async def test_record_and_snapshot(self):
        """单元测试：record 后 snapshot 应正确反映数据。"""
        stats = token_stats
        stats.reset()

        await stats.record("test-model", 100, 50)
        snap = stats.snapshot()

        assert snap["total_requests"] == 1
        assert snap["total_tokens"] == 150
        assert snap["by_model"]["test-model"]["prompt_tokens"] == 100
        assert snap["by_model"]["test-model"]["completion_tokens"] == 50

    @pytest.mark.asyncio
    async def test_concurrent_records(self):
        """并发记录不应导致数据竞争（asyncio.Lock 保护）。"""
        import asyncio

        stats = token_stats
        stats.reset()

        tasks = [
            stats.record("concurrent-model", prompt_tokens=1, completion_tokens=1)
            for _ in range(50)
        ]
        await asyncio.gather(*tasks)

        snap = stats.snapshot()
        assert snap["total_requests"] == 50
        assert snap["total_tokens"] == 100
