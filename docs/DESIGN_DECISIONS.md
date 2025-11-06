# 技术决策记录 (Design Decisions)

> 记录关键架构决策，包括问题、方案、理由和备选

---

## 1. LangGraph 多租户隔离方案

### 问题
- LangGraph 线程如何映射到用户？
- 多租户环境下如何保证状态隔离？

### 搜索结论 (来源: LangChain Forum)

| 方案 | 说明 | 推荐度 |
|------|------|--------|
| InMemoryStore | 默认内存存储，无法生产级隔离 | ❌ |
| InMemoryStore (默认) | 无状态隔离，不适合生产 | ❌ |
| 外部 MySQL + AIOMySQLSaver | 社区维护，与项目 MySQL 统一 | ✅✅ |
| 命名空间隔离 | thread_id = `f"{tenant_id}:{conversation_id}"` | ✅✅ |
| Metadata 注入 | 在 config 中添加 user_id 便于追踪 | ✅ |

> 📦 依赖包：`langgraph-checkpoint-mysql`（社区包，MIT 协议，截至 2025-01 最新版 2.0.12）
> 整个项目统一使用 MySQL 8，无需额外引入 PostgreSQL，降低运维复杂度。

### 最终方案

```python
# pip install langgraph-checkpoint-mysql aiomysql
from langgraph.checkpoint.mysql.aio import AIOMySQLSaver

DB_URI = "mysql://nexus:nexus_pass@localhost:3306/nexus_agent"

async def create_agent():
    async with AIOMySQLSaver.from_conn_string(DB_URI) as checkpointer:
        # 首次使用需 setup（建表）
        await checkpointer.setup()
        graph = build_graph()
        graph.checkpointer = checkpointer

        # 线程命名空间：租户:会话
        thread_id = f"{tenant_id}:{conversation_id}"

        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": "",
                "tenant_id": tenant_id,   # metadata，用于追踪
            }
        }
        return graph, config
```

### checkpoint 相关表（由 setup() 自动创建）

| 表名 | 作用 |
|------|------|
| `checkpoints` | 每个 thread 的最新 checkpoint |
| `checkpoint_blobs` | 序列化的 channel 状态 blob |
| `checkpoint_writes` | pending writes 队列 |

### 备选
- PyMySQLSaver（同步版，适合非异步代码路径）
- 自定义实现 BaseCheckpointSaver（如需定制化 TTL 清理策略）

---

## 2. Milvus BM25 + RRF 混合搜索实现

### 问题
- 如何实现关键词 + 向量的混合检索？
- RRF 参数如何调优？

### 搜索结论 (来源: Milvus 官方文档 + LangChain)

Milvus 2.4+ 原生支持 hybrid_search + RRF reranking：

```python
from langchain_milvus import Milvus
from langchain_milvus.utils.sparse import BM25BuiltInFunction

# 创建支持混合搜索的 VectorStore
vectorstore = Milvus.from_documents(
    documents=docs,
    embedding=[dense_embedding, sparse_embedding],  # 两个 embedding
    builtin_function=BM25BuiltInFunction(output_field_names="sparse"),
    index_params=[dense_index_param, sparse_index_param],
    vector_field=["dense_vector", "sparse_vector"],
)

# 查询时自动 RRF 合并
results = vectorstore.similarity_search(
    query, 
    k=10, 
    ranker_type="rrf", 
    ranker_params={"k": 100}
)
```

### 技术细节

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| RRF k | 60-100 | 较大的 k 值适合候选集较大的场景 |
| dense 索引 | HNSW + COSINE | 语义相似度 |
| sparse 索引 | BM25 + AUTOINDEX | 关键词匹配 |
| top_k | 10-50 | 最终返回数量 |

### 最终方案
- 使用 langchain_milvus 库 (Milvus 官方)
- embedding: BGE-M3 (dense) + 内置 BM25 (sparse)
- RRF k=60 作为起始调优点

---

## 3. Spring Cloud Gateway 多租户 RBAC 架构

### 问题
- 如何在微服务架构中传递租户上下文？
- 如何设计可扩展的 RBAC 模型？

### 搜索结论 (来源: 多篇技术博客 + AWS 最佳实践)

**核心架构：**

```
请求 → Gateway → 提取 Tenant ID → TenantContext (ThreadLocal)
                                    ↓
                          各微服务通过 AOP/Interceptor 获取
```

**实现要点：**

1. **TenantContext 存储**
```java
public class TenantContext {
    private static final ThreadLocal<String> CURRENT_TENANT = new ThreadLocal<>();
    
    public static String getCurrentTenant() { return CURRENT_TENANT.get(); }
    public static void setCurrentTenant(String tenantId) { CURRENT_TENANT.set(tenantId); }
    public static void clear() { CURRENT_TENANT.remove(); }
}
```

2. **Gateway Filter 提取 Tenant ID**
   - 优先级：JWT claim > X-Tenant-ID header > URL path
   - JWT 必须包含 tenant_id claim

3. **RBAC 权限模型**
```
Actor (user + tenant_context) → Action → Resource (tenant-scoped)
```

4. **缓存设计** (重要！)
   - 缓存 key 必须包含 tenant_id: `perm:{tenantId}:{userId}`
   - 否则会导致跨租户泄露

### 最终方案
- Gateway: 负责 JWT 验证 + Tenant ID 提取 + 路由
- Auth Service: 负责登录、JWT 签发
- 每个微服务: 通过 @Tenantaware 注解或 AOP 获取上下文
- 权限缓存: Redis，key 格式 `rbac:{tenantId}:{userId}:{resource}`

---

## 4. Java ↔ Python 微服务通信方案

### 问题
- 同步调用选 gRPC 还是 REST？
- AI 流式输出如何穿透到前端？

### 搜索结论

| 场景 | 协议 | 理由 |
|------|------|------|
| Java → Python (同步调用) | **gRPC** | 类型安全、效率高、双向流 |
| Python → 前端 (流式输出) | **SSE** | 原生支持、浏览器友好、简单 |
| 异步任务队列 | RabbitMQ | 解耦、削峰 |

### 详细设计

**gRPC (Java ↔ Python):**
```protobuf
// agent.proto
service AgentService {
    rpc ExecuteAgent(AgentRequest) returns (stream AgentResponse);
    rpc CheckStatus(TaskId) returns (TaskStatus);
}
```

**SSE (Python → 前端):**
```python
from fastapi import FastAPI
from fastapi.sse import EventSourceResponse

@app.post("/chat/stream")
async def stream_chat(prompt: Prompt) -> AsyncIterable[ServerSentEvent]:
    async def event_generator():
        async for chunk in agent.stream(prompt):
            yield ServerSentEvent(data=json.dumps(chunk))
    
    return EventSourceResponse(event_generator())
```

### 最终方案

| 通信路径 | 协议 |
|---------|------|
| Gateway → Python (REST API) | HTTP/gRPC |
| Python Agent 内部流式 | LangGraph stream |
| Python → 前端 | SSE |
| 异步任务触发 | RabbitMQ |
| 事件通知 | WebSocket (可选) |

---

## 5. 多租户数据隔离策略

### 问题
- MySQL 租户数据隔离：行级 vs Schema 级？
- Milvus 租户隔离：Collection 分区 vs metadata filter？

### 决策

| 层级 | 策略 | 理由 |
|------|------|------|
| MySQL | **行级隔离** (tenant_id 列) | 简单、运维成本低、足够安全 |
| Redis | **key 前缀隔离** | `nexus:{tenantId}:{resource}` |
| Milvus | **metadata filter** | 避免 Collection 爆炸，支持灵活查询 |

### MySQL 隔离示例
```sql
-- 每个表必须有 tenant_id 列
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    username VARCHAR(50),
    ...
);

-- 查询必须带 tenant_id 过滤
SELECT * FROM users WHERE tenant_id = ? AND id = ?;
```

### Milvus 隔离示例
```python
# 写入时添加 tenant_id metadata
vectorstore.add_texts(
    texts=["doc1", "doc2"],
    metadatas=[{"tenant_id": "t1"}, {"tenant_id": "t2"}]
)

# 查询时强制过滤
results = vectorstore.similarity_search(
    query, 
    k=10,
    filter="tenant_id == 't1'"  # 强制租户过滤
)
```

---

## 决策时间线

| 日期 | 决策项 | 最终方案 | 备注 |
|------|--------|----------|------|
| 2026-03-17 | LangGraph 多租户 | MySQL + 命名空间隔离 | AIOMySQLSaver (langgraph-checkpoint-mysql) |
| 2026-03-17 | RAG 混合搜索 | Milvus 原生 RRF | BGE-M3 + BM25 |
| 2026-03-17 | 多租户 RBAC | JWT + ThreadLocal + Redis | key 必须含 tenant |
| 2026-03-17 | 通信协议 | gRPC + SSE | 服务间 / 流式输出 |
| 2026-03-17 | 数据隔离 | 行级 + metadata filter | MySQL + Milvus |
