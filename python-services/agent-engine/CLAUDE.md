# CLAUDE.md — python-services/agent-engine

> 本文件由帕托莉维护，Claude Code 必须在开始前完整阅读。

---

## 服务职责

`agent-engine` 是 Python 核心 AI 服务，负责：
1. LangGraph Agent 图的构建与执行
2. 多租户会话状态管理（MySQL checkpointer）
3. 流式输出（SSE）
4. 工具调用编排

**不负责：** 用户认证（由 Java Gateway 完成）、知识库管理（由 rag-service 负责）

---

## 技术约束

| 约束 | 说明 |
|------|------|
| **必须使用** | Python 3.12, FastAPI, LangGraph 1.1.x |
| **必须使用** | langgraph-checkpoint-mysql 3.x (AIOMySQLSaver) |
| **必须使用** | pydantic v2 数据验证 |
| **数据库** | MySQL 127.0.0.1:3306/nexus_agent, user=nexus, pass=nexus_pass |
| **缓存** | Redis 127.0.0.1:6379 |
| **禁止** | 不允许在 Agent 内直接访问数据库用户表（跨服务边界） |
| **禁止** | 全局共享 LangGraph Graph 实例（每次 invoke 用独立 config） |
| **端口** | 8001 |

---

## 容器内环境

```
向量库: chromadb (内存/文件模式，无需外部服务)
Embedding: sentence-transformers (本地模型，无需 API Key)
LLM 调用: openai SDK (Copilot Hub 代理)
  - base_url: https://copilot.lab.2ndelement.tech/v1
  - api_key: lab-sk-ABiGIb07yUVzIYrd0oXYwAyH2tmW0zwd
  - model: gpt-4o
```

---

## 当前任务

### Task-05: 实现 agent-engine 基础服务

**交付物：**

```
python-services/agent-engine/
├── requirements.txt
├── main.py                   # FastAPI 入口
├── app/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── chat.py       # SSE 流式对话接口
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── graph.py          # LangGraph 图定义
│   │   ├── state.py          # AgentState TypedDict
│   │   └── nodes.py          # 图节点函数
│   ├── checkpointer.py       # MySQL checkpointer 初始化
│   ├── schemas.py            # Pydantic 请求/响应模型
│   └── config.py             # 配置（从环境变量读取）
└── tests/
    ├── test_api.py            # API 层测试
    ├── test_graph.py          # LangGraph 图测试
    └── test_checkpointer.py   # Checkpointer 隔离测试
```

**核心接口：**

```python
# POST /api/v1/agent/chat/stream
# Request Header: X-Tenant-Id: t1, X-User-Id: u1, X-Conv-Id: conv1
# Body: { "message": "你好" }
# Response: text/event-stream

# SSE 事件格式:
data: {"type": "chunk", "content": "你"}
data: {"type": "chunk", "content": "好"}
data: {"type": "done", "conversation_id": "conv1"}
data: {"type": "error", "message": "xxx"}
```

**AgentState 定义：**

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    tenant_id: str
    user_id: str
    conversation_id: str
```

**多租户隔离设计（核心！）：**

```python
thread_id = f"{tenant_id}:{conversation_id}"  # 必须这样！

config = {
    "configurable": {
        "thread_id": thread_id,
        "checkpoint_ns": "",
    }
}

# 调用时
async for event in graph.astream_events(input, config):
    ...
```

---

## 测试要求

**必须覆盖的场景：**
- [ ] 正常对话：发送消息 → 收到流式 SSE 响应
- [ ] 多租户隔离：租户A 的会话历史不影响租户B 同 conv_id
  ```python
  # 租户A 对话后，租户B 用同 conversation_id 对话，历史应为空
  ```
- [ ] 会话连续性：同 tenant+conversation_id 第二轮能看到第一轮历史
- [ ] MySQL checkpointer 持久化：Agent 执行后 DB 中有 checkpoint 记录
- [ ] 无效输入（空消息）→ 422 错误

**测试使用：**
- `pytest` + `pytest-asyncio`
- FastAPI `TestClient` 用于 API 测试
- 测试用真实 MySQL（127.0.0.1:3306/nexus_agent）或 Mock

---

## Code Review 检查清单

- [ ] thread_id 格式是否严格为 `f"{tenant_id}:{conversation_id}"`
- [ ] ChromaDB 查询是否携带 `where={"tenant_id": tenant_id}`
- [ ] SSE 异常时是否发送 `data: {"type": "error", ...}` 而非直接断连
- [ ] 所有路由是否从 Header 中获取 tenant_id（非用户自填）
- [ ] config.py 中无硬编码密钥
- [ ] asyncio 操作有超时保护

---

## 注意事项

1. 先输出 graph.py 的图结构设计（节点/边/状态流），等帕托莉确认再实现
2. LLM 调用用 OpenAI SDK（Base URL 指向 Copilot Hub），Key 从环境变量读
3. 测试时 LLM 调用可用 Mock（避免消耗 API 配额）
4. 生成代码后运行 `python -m pytest tests/ -v` 报告结果
