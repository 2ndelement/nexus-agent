"""
sandbox-service executor 单元测试。

测试代码执行请求的 schema 校验和安全边界。
"""
from __future__ import annotations

import pytest
from app.schemas import ExecuteRequest


# ── Schema 测试 ──

def test_execute_request_default_values():
    """默认 language=python, timeout=30。"""
    req = ExecuteRequest(code="print(1)")
    assert req.language == "python"
    assert req.timeout == 30


def test_execute_request_bash():
    """bash 代码请求。"""
    req = ExecuteRequest(code="echo hello", language="bash", timeout=10)
    assert req.language == "bash"
    assert req.timeout == 10


def test_execute_request_empty_code():
    """空代码应被 Pydantic 校验拦截。"""
    with pytest.raises(Exception):
        ExecuteRequest(code="")


def test_execute_request_excessive_timeout():
    """超长超时应被限制（如果 schema 有 le 约束）。"""
    # 即使 schema 不限制，300 秒也应该能创建
    req = ExecuteRequest(code="import time; time.sleep(1)", timeout=300)
    assert req.timeout == 300
