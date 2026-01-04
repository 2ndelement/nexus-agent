"""
tests/conftest.py — pytest 公共夹具
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.token_stats import token_stats
from main import app


@pytest.fixture(autouse=True)
def reset_stats():
    """每个测试前重置 Token 统计，保证测试隔离。"""
    token_stats.reset()
    yield
    token_stats.reset()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)
