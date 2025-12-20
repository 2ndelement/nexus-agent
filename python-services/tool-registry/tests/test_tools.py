"""
tool-registry pytest 测试套件。

测试策略：
- 使用 SQLite 内存数据库（无需 MySQL）
- httpx AsyncClient 测试 FastAPI 路由
- calculator 和 web_search 工具使用真实逻辑，web_search 的网络调用 Mock
"""

from __future__ import annotations

import json
import sys
import os

# 确保 tool-registry 根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── 测试数据库（SQLite 内存）──────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_engine():
    from services.tool_service import Base
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_session_factory(test_engine):
    return sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="function")
def test_db(test_session_factory):
    db = test_session_factory()
    try:
        yield db
    finally:
        db.close()


# ── FastAPI 测试客户端 ────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def client(test_session_factory):
    """配置好测试数据库的 FastAPI TestClient"""
    from main import app
    from routers.tools import set_session_factory
    from services.tool_service import seed_builtin_tools

    # 注入测试 session factory
    set_session_factory(test_session_factory)

    # 初始化内置工具
    db = test_session_factory()
    try:
        seed_builtin_tools(db)
    finally:
        db.close()

    with TestClient(app) as c:
        yield c


# ══════════════════════════════════════════════════════════════════════════════
# 1. calculator 内置工具测试
# ══════════════════════════════════════════════════════════════════════════════

class TestCalculator:

    def test_basic_addition(self):
        from builtin_tools.calculator import calculate
        result = calculate("2 + 3")
        assert result["result"] == 5
        assert result["expression"] == "2 + 3"

    def test_multiplication(self):
        from builtin_tools.calculator import calculate
        result = calculate("2 + 3 * 4")
        assert result["result"] == 14  # 按运算符优先级

    def test_power(self):
        from builtin_tools.calculator import calculate
        result = calculate("2 ** 10")
        assert result["result"] == 1024

    def test_sqrt_function(self):
        from builtin_tools.calculator import calculate
        result = calculate("sqrt(16)")
        assert result["result"] == 4

    def test_float_result(self):
        from builtin_tools.calculator import calculate
        result = calculate("1 / 3")
        assert abs(result["result"] - 1/3) < 1e-9

    def test_nested_expression(self):
        from builtin_tools.calculator import calculate
        result = calculate("(1 + 2) * (3 + 4)")
        assert result["result"] == 21

    def test_empty_expression_raises(self):
        from builtin_tools.calculator import calculate
        with pytest.raises(ValueError, match="不能为空"):
            calculate("")

    def test_division_by_zero_raises(self):
        from builtin_tools.calculator import calculate
        with pytest.raises(ZeroDivisionError):
            calculate("1 / 0")

    def test_invalid_function_raises(self):
        from builtin_tools.calculator import calculate
        with pytest.raises(ValueError, match="不允许"):
            calculate("__import__('os')")

    def test_modulo(self):
        from builtin_tools.calculator import calculate
        result = calculate("10 % 3")
        assert result["result"] == 1

    def test_pi_constant(self):
        from builtin_tools.calculator import calculate
        import math
        result = calculate("pi")
        assert abs(result["result"] - math.pi) < 1e-9


# ══════════════════════════════════════════════════════════════════════════════
# 2. web_search 内置工具测试（Mock 网络调用）
# ══════════════════════════════════════════════════════════════════════════════

class TestWebSearch:

    @pytest.mark.anyio
    async def test_web_search_returns_results(self, monkeypatch):
        """Mock DuckDuckGo API，验证结果结构"""
        import builtin_tools.web_search as ws_module

        # Mock httpx AsyncClient at the module level where it's used
        class MockResponse:
            status_code = 200
            def raise_for_status(self): pass
            def json(self):
                return {
                    "AbstractText": "Python 是一种高级编程语言。",
                    "Heading": "Python",
                    "AbstractURL": "https://www.python.org",
                    "RelatedTopics": [],
                    "Answer": "",
                }

        class MockAsyncClient:
            def __init__(self, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def get(self, *args, **kwargs): return MockResponse()

        monkeypatch.setattr(ws_module.httpx, "AsyncClient", MockAsyncClient)

        result = await ws_module.web_search("Python")
        assert result["query"] == "Python"
        assert len(result["results"]) >= 1
        assert "snippet" in result["results"][0]
        assert "url" in result["results"][0]

    @pytest.mark.anyio
    async def test_web_search_empty_query_raises(self):
        from builtin_tools.web_search import web_search
        with pytest.raises(ValueError, match="不能为空"):
            await web_search("")

    @pytest.mark.anyio
    async def test_web_search_mock_fallback(self, monkeypatch):
        """网络不可用时，返回 mock 结果"""
        import builtin_tools.web_search as ws_module

        class FailingAsyncClient:
            def __init__(self, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def get(self, *args, **kwargs):
                raise ws_module.httpx.ConnectError("Connection refused")

        monkeypatch.setattr(ws_module.httpx, "AsyncClient", FailingAsyncClient)

        result = await ws_module.web_search("test query")
        assert result["query"] == "test query"
        assert len(result["results"]) > 0
        assert result.get("note") == "mock_results"

    @pytest.mark.anyio
    async def test_web_search_max_results(self, monkeypatch):
        """验证 max_results 参数限制"""
        import builtin_tools.web_search as ws_module

        class FailingAsyncClient:
            def __init__(self, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def get(self, *args, **kwargs):
                raise ws_module.httpx.ConnectError("Connection refused")

        monkeypatch.setattr(ws_module.httpx, "AsyncClient", FailingAsyncClient)

        result = await ws_module.web_search("query", max_results=2)
        assert len(result["results"]) <= 2


# ══════════════════════════════════════════════════════════════════════════════
# 3. ToolService 服务层测试
# ══════════════════════════════════════════════════════════════════════════════

class TestToolService:

    def test_register_builtin_tool(self, test_db):
        from services.tool_service import ToolService, seed_builtin_tools
        seed_builtin_tools(test_db)
        service = ToolService(test_db)

        # 查询 calculator
        tool = service.get_tool("calculator")
        assert tool is not None
        assert tool.name == "calculator"
        assert tool.scope.value == "BUILTIN"
        assert tool.tenant_id is None

    def test_register_tenant_tool(self, test_db):
        from services.tool_service import ToolService
        from models import RegisterToolRequest, ToolDefinition, ParameterSchema, ToolScope
        service = ToolService(test_db)

        req = RegisterToolRequest(
            tool=ToolDefinition(
                name="my_tool",
                description="租户自定义工具",
                parameters=ParameterSchema(
                    properties={"input": {"type": "string", "description": "输入"}},
                    required=["input"],
                ),
            ),
            scope=ToolScope.TENANT,
        )
        tool = service.register_tool(req, tenant_id=1)
        test_db.commit()

        assert tool.name == "my_tool"
        assert tool.tenant_id == 1
        assert tool.scope.value == "TENANT"

    def test_list_tools_multi_tenant_isolation(self, test_db):
        """租户A的工具对租户B不可见，内置工具对所有租户可见"""
        from services.tool_service import ToolService, seed_builtin_tools
        from models import RegisterToolRequest, ToolDefinition, ParameterSchema, ToolScope

        seed_builtin_tools(test_db)
        service = ToolService(test_db)

        # 为租户1注册工具
        req = RegisterToolRequest(
            tool=ToolDefinition(
                name="tenant1_tool",
                description="租户1专属工具",
                parameters=ParameterSchema(),
            ),
            scope=ToolScope.TENANT,
        )
        service.register_tool(req, tenant_id=1)
        test_db.commit()

        # 租户1可以看到：内置工具 + 自己的工具
        tools_t1 = service.list_tools(tenant_id=1)
        names_t1 = [t.name for t in tools_t1]
        assert "calculator" in names_t1
        assert "web_search" in names_t1
        assert "tenant1_tool" in names_t1

        # 租户2只能看到内置工具，看不到租户1的工具
        tools_t2 = service.list_tools(tenant_id=2)
        names_t2 = [t.name for t in tools_t2]
        assert "calculator" in names_t2
        assert "tenant1_tool" not in names_t2

    def test_register_tool_idempotent(self, test_db):
        """重复注册同名工具更新描述，不创建重复记录"""
        from services.tool_service import ToolService
        from models import RegisterToolRequest, ToolDefinition, ParameterSchema, ToolScope

        service = ToolService(test_db)
        req = RegisterToolRequest(
            tool=ToolDefinition(
                name="dup_tool",
                description="原始描述",
                parameters=ParameterSchema(),
            ),
            scope=ToolScope.TENANT,
        )
        service.register_tool(req, tenant_id=1)
        test_db.commit()

        # 更新描述
        req2 = RegisterToolRequest(
            tool=ToolDefinition(
                name="dup_tool",
                description="更新后的描述",
                parameters=ParameterSchema(),
            ),
            scope=ToolScope.TENANT,
        )
        updated = service.register_tool(req2, tenant_id=1)
        test_db.commit()

        assert updated.description == "更新后的描述"
        # 只有一条记录
        tools = service.list_tools(tenant_id=1)
        dup_tools = [t for t in tools if t.name == "dup_tool"]
        assert len(dup_tools) == 1

    def test_delete_tenant_tool(self, test_db):
        from services.tool_service import ToolService
        from models import RegisterToolRequest, ToolDefinition, ParameterSchema, ToolScope

        service = ToolService(test_db)
        req = RegisterToolRequest(
            tool=ToolDefinition(
                name="del_tool",
                description="待删除工具",
                parameters=ParameterSchema(),
            ),
            scope=ToolScope.TENANT,
        )
        service.register_tool(req, tenant_id=1)
        test_db.commit()

        deleted = service.delete_tool("del_tool", tenant_id=1)
        test_db.commit()
        assert deleted is True

        tool = service.get_tool("del_tool", tenant_id=1)
        assert tool is None

    def test_delete_builtin_tool_raises(self, test_db):
        from services.tool_service import ToolService, seed_builtin_tools
        seed_builtin_tools(test_db)
        service = ToolService(test_db)

        with pytest.raises(PermissionError, match="内置工具不允许删除"):
            service.delete_tool("calculator", tenant_id=None)

    @pytest.mark.anyio
    async def test_execute_calculator(self, test_db):
        from services.tool_service import ToolService, seed_builtin_tools
        from models import ExecuteToolRequest

        seed_builtin_tools(test_db)
        service = ToolService(test_db)

        req = ExecuteToolRequest(name="calculator", arguments={"expression": "2 + 3 * 4"})
        result = await service.execute_tool(req)

        assert result.success is True
        assert result.result["result"] == 14

    @pytest.mark.anyio
    async def test_execute_nonexistent_tool(self, test_db):
        from services.tool_service import ToolService, seed_builtin_tools
        from models import ExecuteToolRequest

        seed_builtin_tools(test_db)
        service = ToolService(test_db)

        req = ExecuteToolRequest(name="nonexistent_tool", arguments={})
        result = await service.execute_tool(req)

        assert result.success is False
        assert "不存在" in result.error

    @pytest.mark.anyio
    async def test_execute_calculator_invalid_expr(self, test_db):
        from services.tool_service import ToolService, seed_builtin_tools
        from models import ExecuteToolRequest

        seed_builtin_tools(test_db)
        service = ToolService(test_db)

        req = ExecuteToolRequest(name="calculator", arguments={"expression": "invalid!!!"})
        result = await service.execute_tool(req)

        assert result.success is False
        assert result.error is not None


# ══════════════════════════════════════════════════════════════════════════════
# 4. API 路由层测试（FastAPI TestClient）
# ══════════════════════════════════════════════════════════════════════════════

class TestToolsAPI:

    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_list_tools_returns_builtins(self, client):
        """GET /api/tools 应返回内置工具"""
        resp = client.get("/api/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        tool_names = [t["name"] for t in data["data"]]
        assert "calculator" in tool_names
        assert "web_search" in tool_names

    def test_get_tool_calculator(self, client):
        """GET /api/tools/calculator → 200 + tool details"""
        resp = client.get("/api/tools/calculator")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["name"] == "calculator"
        assert "parameters" in data["data"]

    def test_get_tool_not_found(self, client):
        """GET /api/tools/nonexistent → 404"""
        resp = client.get("/api/tools/nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 404

    def test_register_tenant_tool(self, client):
        """POST /api/tools 注册租户工具 → 200"""
        payload = {
            "tool": {
                "name": "my_custom_tool",
                "description": "自定义测试工具",
                "parameters": {
                    "type": "object",
                    "properties": {"input": {"type": "string"}},
                    "required": ["input"],
                }
            },
            "scope": "TENANT"
        }
        resp = client.post(
            "/api/tools",
            json=payload,
            headers={"X-Tenant-Id": "1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["name"] == "my_custom_tool"
        assert data["data"]["tenant_id"] == 1

    def test_register_tenant_tool_without_tenant_id_fails(self, client):
        """注册租户工具时不传 X-Tenant-Id → 400"""
        payload = {
            "tool": {"name": "bad_tool", "description": "bad"},
            "scope": "TENANT"
        }
        resp = client.post("/api/tools", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 400

    def test_tenant_tool_isolation(self, client):
        """租户1的工具对租户2不可见"""
        payload = {
            "tool": {
                "name": "tenant1_exclusive",
                "description": "租户1专属工具",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            "scope": "TENANT"
        }
        # 租户1注册
        client.post("/api/tools", json=payload, headers={"X-Tenant-Id": "1"})

        # 租户1可见
        resp1 = client.get("/api/tools", headers={"X-Tenant-Id": "1"})
        names1 = [t["name"] for t in resp1.json()["data"]]
        assert "tenant1_exclusive" in names1

        # 租户2不可见
        resp2 = client.get("/api/tools", headers={"X-Tenant-Id": "2"})
        names2 = [t["name"] for t in resp2.json()["data"]]
        assert "tenant1_exclusive" not in names2

    def test_execute_calculator_via_api(self, client):
        """POST /api/tools/execute calculator → success"""
        payload = {
            "name": "calculator",
            "arguments": {"expression": "10 * 10 + 5"},
        }
        resp = client.post("/api/tools/execute", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        result = data["data"]
        assert result["success"] is True
        assert result["result"]["result"] == 105

    def test_execute_calculator_division(self, client):
        """POST /api/tools/execute calculator 除法"""
        payload = {
            "name": "calculator",
            "arguments": {"expression": "22 / 7"},
        }
        resp = client.post("/api/tools/execute", json=payload)
        data = resp.json()
        assert data["data"]["success"] is True
        assert abs(data["data"]["result"]["result"] - 22/7) < 1e-6

    def test_execute_calculator_invalid(self, client):
        """POST /api/tools/execute calculator 非法表达式 → success=False"""
        payload = {
            "name": "calculator",
            "arguments": {"expression": "os.system('ls')"},
        }
        resp = client.post("/api/tools/execute", json=payload)
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["success"] is False

    def test_delete_tenant_tool(self, client):
        """DELETE /api/tools/{name} 删除租户工具 → 200"""
        # 先注册
        payload = {
            "tool": {"name": "deletable", "description": "删除测试"},
            "scope": "TENANT"
        }
        client.post("/api/tools", json=payload, headers={"X-Tenant-Id": "5"})

        # 删除
        resp = client.delete("/api/tools/deletable", headers={"X-Tenant-Id": "5"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200

    def test_delete_builtin_tool_forbidden(self, client):
        """DELETE /api/tools/calculator → 403（内置工具不允许删除）"""
        resp = client.delete("/api/tools/calculator", headers={"X-Tenant-Id": "1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 403

    def test_delete_nonexistent_tool_returns_404(self, client):
        """DELETE /api/tools/ghost → 404"""
        resp = client.delete("/api/tools/ghost", headers={"X-Tenant-Id": "1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 404
