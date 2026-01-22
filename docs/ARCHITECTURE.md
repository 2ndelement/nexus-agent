# NexusAgent 架构设计文档

> 基于技术调研结论的最终技术选型与各层设计

---

## 1. 系统架构总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           接入层 (Clients)                                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────┐  │
│  │  WebChat │  │   QQ    │  │  飞书   │  │  Discord │  │  REST API   │  │
│  │  (Vue3)  │  │ (OneBot)│  │  SDK    │  │   SDK    │  │  (第三方)   │  │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └──────┬──────┘  │
└───────┼────────────┼────────────┼────────────┼───────────────┼──────────┘
        │            │            │            │               │
        └────────────┴────────────┼────────────┴───────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Spring Cloud Gateway                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │  JWT 验证   │  │  Tenant ID   │  │   限流      │                   │
│  │  (Auth)     │  │  提取注入    │  │  (Sentinel) │                   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                   │
└─────────┼─────────────────┼─────────────────┼────────────────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Java 微服务层                                   │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │  Auth  │  │ Tenant │  │Session │  │Knowledge│  │ Config │        │
│  │ 认证服务 │  │租户服务 │  │会话服务 │  │知识库服务│  │Agent配置│        │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
│       │            │            │            │            │             │
│  ┌────┴────────────┴────────────┴────────────┴────────────┴────┐        │
│  │                    Nacos (服务注册与配置)                    │        │
│  └─────────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────┘
                    │                        │ (gRPC/REST)
                    │ gRPC                   ▼
                    ▼              ┌─────────────────────────┐
┌────────────────────────────────┤   Python AI 服务层         ├────────────┐
│                                │                          │            │
│  ┌─────────────────┐  ┌──────┴──────┐  ┌──────────────┐  │            │
│  │  Agent Engine   │  │  LLM Proxy  │  │ RAG Service  │  │            │
│  │  (LangGraph)    │  │  (LLM调用)  │  │ (混合检索)   │  │            │
│  └────────┬────────┘  └─────────────┘  └──────┬───────┘  │            │
│           │                                   │           │            │
│  ┌────────┴────────┐                ┌────────┴────────┐   │            │
│  │  Tool Registry │                │ Memory Service │   │            │
│  │  (工具注册)    │                │ (会话记忆)     │   │            │
│  └─────────────────┘                └────────────────┘   │            │
└──────────────────────────────────────────────────────────┴──────────────┘
                    │
                    ▼ (消息队列)
┌─────────────────────────────────────────────────────────────────────────┐
│                          基础设施层                                       │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │ MySQL 8 │  │ Redis   │  │Milvus  │  │RabbitMQ│  │ MinIO   │        │
│  │(租户数据)│  │(缓存/会话)│  │(向量库)│  │(消息队列)│  │(文件存储)│        │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │            Prometheus + Grafana (监控)                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心模块设计

### 2.1 认证与授权 (Auth Service)

**职责：** 用户登录、JWT 签发、Token 刷新

**技术栈：** Spring Boot 3 + Spring Security + Redis

**关键设计：**
```java
// JWT 包含的信息
Claims {
    "sub": "user_id",
    "tenant_id": "tenant_123",
    "roles": ["ADMIN", "USER"],
    "permissions": ["chat:read", "chat:write", "knowledge:admin"]
}
```

**Token 类型：**
| 类型 | 有效期 | 用途 |
|------|--------|------|
| Access Token | 2 小时 | API 调用 |
| Refresh Token | 7 天 | 刷新 Access Token |

---

### 2.2 租户服务 (Tenant Service)

**职责：** 租户 CRUD、租户配置、计费套餐

**数据模型：**
```
Tenant (租户)
├── id: UUID
├── name: String
├── plan: Enum (FREE, PRO, ENTERPRISE)
├── quota: JSON (max_users, max_agents, max_api_calls)
└── settings: JSON (custom_config)

TenantUser (租户用户)
├── tenant_id: FK
├── user_id: FK
├── role: Enum (OWNER, ADMIN, MEMBER)
└── status: Enum (ACTIVE, INVITED, DISABLED)
```

---

### 2.3 会话服务 (Session Service)

**职责：** 对话管理、上下文管理、历史消息

**技术点：**
- 对话按租户隔离
- 支持多轮对话
- 消息持久化到 MySQL
- 会话状态缓存到 Redis

---

### 2.4 知识库服务 (Knowledge Service)

**职责：** 文档上传、分片、向量化、RAG 检索

**技术架构：**
```
文档上传 → 文本提取 → 分片 → Embedding (BGE-M3) 
         → Milvus 存储 + MySQL 元数据 → RAG 检索
```

**RAG 混合检索流程：**
```
Query → BM25 检索 (sparse) → 向量检索 (dense) 
      → RRF 合并 (k=60) → 重排序 → 返回结果
```

---

### 2.5 Agent 引擎 (Python)

**职责：** LangGraph 图执行、工具调用、LLM 调用

**Tool Calling 架构（v2 优化新增）：**

```
START → call_llm → [should_continue] ─── has tool_calls ──→ tool_call_node ─┐
                         │                                                    │
                         └── no tool_calls → END               call_llm ←─────┘
```

- `call_llm_node`：调用 LLM，绑定 calculator / web_search / sandbox_execute 工具定义
- `tool_call_node`：解析 AIMessage.tool_calls，通过 HTTP 调用 tool-registry 执行
- `should_continue`：条件路由，有 tool_calls 则循环，否则结束
- `max_tool_iterations`：防止无限循环的安全阀

**核心架构：**
```python
# Agent 状态定义
class AgentState(TypedDict):
    messages: list[BaseMessage]
    tenant_id: str
    user_id: str
    conversation_id: str
    tools_result: dict

# Checkpoint 持久化 (MySQL)
# pip install langgraph-checkpoint-mysql
from langgraph.checkpoint.mysql.aio import AIOMySQLSaver
checkpointer = AIOMySQLSaver.from_conn_string(
    "mysql://nexus:nexus_pass@localhost:3306/nexus_agent"
)

# 线程命名空间
thread_id = f"{tenant_id}:{conversation_id}"
```

**流式输出：**
```python
# LangGraph stream 穿透到 SSE
async def stream_chat(prompt: str, tenant_id: str):
    async for event in agent.astream_events(prompt, config):
        if event["event"] == "on_chat_model_stream":
            yield f"data: {event['data']['chunk'].content}\n\n"
```

---

### 2.6 LLM 代理 (LLM Proxy)

**职责：** 统一 LLM 调用入口、支持多模型切换、计费统计

**支持模型：**
| 模型 | 用途 | 配置方式 |
|------|------|----------|
| OpenAI (GPT-4o) | 默认 | API Key |
| Anthropic (Claude) | 备选 | API Key |
| Ollama | 本地部署 | Host/Port |
| Azure OpenAI | 企业版 | API Key + Endpoint |

---

## 3. 多租户隔离设计

### 3.1 数据层隔离

| 存储 | 隔离策略 | 实现方式 |
|------|----------|----------|
| MySQL | 行级隔离 | `tenant_id` 列 + 强制 WHERE 过滤 |
| Redis | Key 前缀 | `nexus:{tenantId}:{key}` |
| Milvus | Metadata Filter | `filter="tenant_id == '{tenant_id}'"` |
| MinIO | 路径隔离 | `/{tenantId}/{bucket}/{path}` |

### 3.2 运行时隔离

```java
// TenantContext (Java)
public class TenantContext {
    private static final ThreadLocal<String> CURRENT_TENANT = new ThreadLocal<>();
    
    public static String getCurrentTenant() { 
        return CURRENT_TENANT.get(); 
    }
}

// Python 端通过 JWT 获取
def get_tenant_id(token: str) -> str:
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return payload["tenant_id"]
```

### 3.3 缓存隔离 (重要！)

❌ **错误示例：**
```java
// 缓存 key 缺少 tenant_id，导致跨租户泄露
cache.put("perm:" + userId, permissions);  // 危险！
```

✅ **正确示例：**
```java
// 缓存 key 必须包含 tenant_id
cache.put("rbac:" + tenantId + ":" + userId + ":" + resource, permissions);
```

---

## 4. 通信协议设计

### 4.1 服务间通信

| 路径 | 协议 | 格式 | 说明 |
|------|------|------|------|
| Gateway → Java 服务 | HTTP | JSON | 常规 REST |
| Gateway → Python 服务 | HTTP/gRPC | JSON/Protobuf | Agent 执行 |
| Java → Python (同步) | gRPC | Protobuf | 流式响应 |
| Python → 前端 | SSE | text/event-stream | 实时流式 |
| 异步任务 | RabbitMQ | JSON | 任务队列 |

### 4.2 gRPC 接口定义

```protobuf
// agent.proto
syntax = "proto3";

package nexus.agent;

service AgentService {
    // 流式执行 Agent
    rpc Execute(stream AgentRequest) returns (stream AgentResponse);
    
    // 检查任务状态
    rpc GetTaskStatus(TaskId) returns (TaskStatus);
    
    // 终止任务
    rpc CancelTask(TaskId) returns (CancelResult);
}

message AgentRequest {
    string tenant_id = 1;
    string user_id = 2;
    string conversation_id = 3;
    string prompt = 4;
    map<string, string> context = 5;
}

message AgentResponse {
    string event_type = 1;  // "chunk", "tool_call", "done", "error"
    string content = 2;
    map<string, string> metadata = 3;
}
```

### 4.3 SSE 接口

```python
# Python FastAPI SSE 端点
@app.post("/api/v1/agent/chat/stream")
async def stream_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
) -> StreamingResponse:
    
    async def event_generator():
        async for chunk in agent.execute(
            prompt=request.message,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            conversation_id=request.conversation_id
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

---

## 5. 部署架构

### 5.1 Docker Compose 开发环境

完整的 `docker-compose.yml` 已在项目根目录提供，包含 **19 个服务**：

| 分类 | 服务 | 端口 |
|------|------|------|
| 基础设施 | MySQL 8.0, Redis 7, RabbitMQ 3, ChromaDB | 3306, 6379, 5672/15672, 8000 |
| Java 微服务 | gateway, auth, tenant, session, platform, agent-config, knowledge, billing | 8080, 8002-8008 |
| Python 微服务 | agent-engine, llm-proxy, tool-registry, memory, rag, embed-worker, sandbox | 8001, 8010-8013, 8020 |

```bash
# 启动
cp .env.example .env   # 填入实际配置
docker compose up -d

# 查看状态
docker compose ps
```

**关键设计：**
- YAML Anchor (`x-java-common`, `x-python-common`) 复用公共配置
- 中间件 healthcheck → 确保服务启动顺序
- `Dockerfile.java` 多阶段构建 → 镜像约 200MB

### 5.2 Kubernetes 生产环境 (规划)

```
┌─────────────────────────────────────────┐
│              Ingress/Nginx               │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│         Spring Cloud Gateway            │
│   (多副本 + HPA 自动扩缩容)              │
└────────────────┬────────────────────────┘
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
┌───────┐   ┌───────┐   ┌───────┐
│Auth Svc│   │Tenant │   │Session│
│ Pod   │   │ Pod   │   │ Pod   │
└───┬───┘   └───┬───┘   └───┬───┘
    │           │           │
    └───────────┼───────────┘
                │
┌───────────────▼───────────────────────┐
│         Python AI Services              │
│  ┌─────────┐  ┌─────────┐  ┌────────┐ │
│  │ Agent    │  │  RAG    │  │  LLM   │ │
│  │ Engine   │  │ Service │  │ Proxy  │ │
│  └─────────┘  └─────────┘  └────────┘ │
└────────────────────────────────────────┘
```

---

## 5.3 端口分配总表

| 端口 | 服务 | 语言 | 说明 |
|------|------|------|------|
| 8080 | nexus-gateway | Java | API 网关统一入口 |
| 8001 | agent-engine | Python | LangGraph Agent 引擎 |
| 8002 | nexus-auth | Java | 认证/登录/注册 |
| 8003 | nexus-tenant | Java | 租户管理 |
| 8004 | nexus-session | Java | 会话/消息管理 |
| 8005 | nexus-platform | Java | 平台适配器 (QQ/WebChat) |
| 8006 | nexus-agent-config | Java | Agent 配置 & 技能 |
| 8007 | nexus-knowledge | Java | 知识库/文档管理 |
| 8008 | nexus-billing | Java | 计费/配额 |
| 8010 | llm-proxy | Python | LLM 多模型路由 |
| 8011 | tool-registry | Python | 工具注册与执行 |
| 8012 | memory-service | Python | 会话记忆 |
| 8013 | rag-service | Python | RAG 检索 |
| 8020 | sandbox-service | Python | 代码沙箱执行 |
| — | embed-worker | Python | 向量化消费者（无 HTTP 端口） |

---

## 5.4 服务注册与发现 (Nacos)

**v3 优化新增：** 所有 Java 微服务注册到 Nacos，实现动态服务发现。

```
┌─────────────────────────────────────────────────────┐
│                    Nacos Server                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐ │
│  │nexus-auth│ │nexus-   │ │nexus-   │ │nexus-    │ │
│  │  :8002  │ │tenant   │ │session  │ │knowledge │ │
│  │         │ │  :8003  │ │  :8004  │ │  :8007   │ │
│  └─────────┘ └─────────┘ └─────────┘ └──────────┘ │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐ │
│  │nexus-   │ │nexus-   │ │nexus-   │ │nexus-    │ │
│  │platform │ │agent-   │ │billing  │ │gateway   │ │
│  │  :8005  │ │config   │ │  :8008  │ │  :8080   │ │
│  └─────────┘ │  :8006  │ └─────────┘ └──────────┘ │
│              └─────────┘                            │
└─────────────────────────────────────────────────────┘
```

- Gateway 使用 `lb://nexus-auth` 等 URI 进行动态路由
- Python 服务暂不注册 Nacos，保持 HTTP 直连（后续可通过 sidecar 接入）

## 5.5 限流与熔断 (Sentinel)

**v3 优化新增：** Gateway 层 Sentinel 限流 + 业务服务 `@SentinelResource` 注解。

| API 分组 | QPS 阈值 | Burst | 说明 |
|----------|---------|-------|------|
| agent_api | 50 | 10 | LLM 调用成本高 |
| auth_api | 20 | 5 | 防暴力破解 |
| knowledge_api | 10 | 3 | 文件处理资源密集 |
| llm_api | 30 | 10 | LLM 代理 |
| 通用路由 | 100 | 20 | tenant/session/billing 等 |

- 限流返回 `429 {"code":429,"msg":"请求过于频繁，请稍后重试"}`
- 可通过 Sentinel Dashboard (`:8858`) 动态调整规则

---

## 6. 安全性设计

### 6.1 认证流程

**JWT 黑名单机制（v2 优化新增）：**

```
登出 → Auth 写入 Redis: nexus:blacklist:{jti} = "1" (TTL = Token剩余有效期)
     ↓
后续请求 → Gateway AuthGlobalFilter 解析 jti → 查 Redis 黑名单
     ↓
命中 → 401 "Token 已失效（已登出）"
未命中 → 放行
```

#### 6.1.1 原认证流程

```
用户登录 → Auth Service → 验证账号密码 
                              ↓
                    生成 JWT (含 tenant_id, roles)
                              ↓
                    返回 Access Token + Refresh Token
                              ↓
        前端每次请求携带 Access Token
                    ↓
        Gateway 验证 Token → 注入 TenantContext → 路由到后端
```

### 6.2 权限模型 (RBAC)

```
用户 → 角色 → 权限
       ↑
    租户范围

权限定义格式：{resource}:{action}
例如：
- chat:read     (查看会话)
- chat:write    (发送消息)
- knowledge:admin (管理知识库)
- agent:config  (配置 Agent)
```

### 6.3 API 安全

| 措施 | 说明 |
|------|------|
| HTTPS only | 生产环境强制 HTTPS |
| JWT 签名 | HS256/RSA256 |
| Token 过期 | Access Token 2h 强制刷新 |
| 限流 | Sentinel 网关限流（4 个 API 分组 + 12 条规则） + Redis 配额计费 |
| 日志审计 | 记录所有敏感操作 |

---

## 7. 监控与运维

### 7.1 指标监控 (Prometheus + Grafana)

| 指标 | 来源 | 告警阈值 |
|------|------|----------|
| QPS | Gateway | > 10000/min |
| P99 延迟 | 各服务 | > 2s |
| 错误率 | 各服务 | > 1% |
| Token 消耗 | LLM Proxy | 租户配额超 80% |

### 7.2 日志链路

```
TraceID (Gateway 生成)
    ↓
Java Services (MDC 记录)
    ↓
Python Services (Context 传递)
    ↓
LangGraph (LangSmith 集成)
```

---

## 8. 技术选型总结

| 层级 | 技术 | 选型理由 |
|------|------|----------|
| 网关 | Spring Cloud Gateway | 成熟、Java 生态、RBAC 友好 |
| 认证 | JWT + Redis | 无状态、高性能 |
| Agent 框架 | LangGraph | 状态流控、生产级 checkpointer |
| RAG | Milvus + BM25 + RRF | 官方混合检索支持 |
| 向量模型 | BGE-M3 | 中英文兼顾、多语言 |
| 流式输出 | SSE | 浏览器原生支持 |
| 服务通信 | gRPC | 类型安全、效率高 |
| 消息队列 | RabbitMQ | 解耦、削峰 |
| 缓存 | Redis | 租户隔离、Session 管理 |

---

## 9. 后续演进

- [ ] MCP (Model Context Protocol) 工具生态
- [ ] 多 Agent 协同 (Supervisor 模式)
- [ ] A2A (Agent to Agent) 协议支持
- [ ] Agent Marketplace (模板市场)
- [ ] 多模态支持 (图像、语音)

---

## 10. 容器内测试环境说明

> 本项目运行在无 Docker 的容器环境中，以下为实际可用的技术栈。

### 10.1 环境清单（已验证 ✅）

| 组件 | 版本 | 运行方式 | 用途 |
|------|------|----------|------|
| **Java** | OpenJDK 21 | 直接运行 | Java 微服务编译 |
| **Maven** | 3.9.9 | 直接运行 | Java 依赖管理 |
| **Python** | 3.12.12 | 直接运行 | Python AI 服务 |
| **FastAPI** | 0.135 | pip | HTTP/SSE 框架 |
| **LangGraph** | 1.1.2 | pip | Agent 执行引擎 |
| **langgraph-checkpoint-mysql** | 3.0.0 | pip | Agent 状态持久化 |
| **MySQL (MariaDB)** | 11.8.6 | 进程启动 | 关系型数据库 |
| **Redis** | 8.0.2 | 进程启动 | 缓存/Session |
| **ChromaDB** | 1.5.2 | pip | 向量数据库（开发） |
| **faiss-cpu** | - | pip | 轻量向量检索 |
| **sentence-transformers** | 5.2.3 | pip | 本地 Embedding 模型 |
| **SQLAlchemy** | 2.0.48 | pip | ORM |
| **pydantic** | 2.12.5 | pip | 数据验证 |

### 10.2 生产 vs 容器内测试对应关系

| 生产规划 | 容器内替代 | 接口兼容 |
|----------|------------|----------|
| Milvus | ChromaDB | 通过 Retriever 抽象层 ✅ |
| 独立 MySQL 服务 | 容器内进程 | 相同连接串 ✅ |
| 独立 Redis 集群 | 容器内单机 Redis | 相同接口 ✅ |
| Nacos 服务发现 | 硬编码配置 (dev profile) | Spring Profile 切换 ✅ |
| RabbitMQ | 内存队列 / asyncio.Queue | 接口抽象隔离 ✅ |
| MinIO | 本地文件系统 | 通过 Storage 抽象层 ✅ |

### 10.3 测试策略

```
单元测试 (Unit)
├── Java: JUnit 5 + H2 内存数据库 + Mockito
└── Python: pytest + TestClient (FastAPI) + 内存 ChromaDB

集成测试 (Integration)
├── Java: Spring Boot Test + 容器内 MySQL/Redis
└── Python: pytest-asyncio + 容器内 MySQL/Redis

端到端测试 (E2E)
└── Python: HTTPx + FastAPI TestClient 模拟全链路
```

### 10.4 服务启动脚本（容器内）

```bash
# 启动 MySQL (MariaDB)
mkdir -p /var/run/mysqld && chown mysql:mysql /var/run/mysqld
mysqld --user=mysql --bind-address=127.0.0.1 --port=3306 &

# 启动 Redis
redis-server --daemonize yes --port 6379

# 初始化数据库用户
mysql -u root -e "CREATE USER IF NOT EXISTS 'nexus'@'%' IDENTIFIED BY 'nexus_pass';"
mysql -u root -e "GRANT ALL PRIVILEGES ON nexus_agent.* TO 'nexus'@'%'; FLUSH PRIVILEGES;"
```

---

## 11. Agent Skill 系统设计

> 对标 `/root/.agents/skills` 规范，用户可自定义 Skill

### 11.1 Skill 目录结构

```
Skill 结构 (对标 .agent/skills):
  {skill-name}/
  ├── SKILL.md              # 必需，YAML frontmatter + Markdown 说明
  ├── scripts/              # 可选，可执行脚本 (Python/Bash)
  ├── references/           # 可选，按需加载的参考文档
  └── assets/               # 可选，输出中使用的资源文件
```

**SKILL.md 格式:**
```yaml
---
name: skill-name
description: "功能说明。适用场景。触发关键词。"
---
# 主体内容 (Markdown)
```

### 11.2 在 NexusAgent 中的实现

```
┌─────────────────────────────────────────────────────────────┐
│                    nexus-agent-config                       │
│                      (Agent 配置服务)                        │
├─────────────────────────────────────────────────────────────┤
│  Skill 存储层                                              │
│  ┌─────────────┐    ┌─────────────┐                      │
│  │   MySQL      │    │   MinIO      │                      │
│  │  元数据表     │    │  SKILL.md    │                      │
│  │  name/desc  │    │  scripts/    │                      │
│  │  tenant_id  │    │  assets/     │                      │
│  └─────────────┘    └─────────────┘                      │
├─────────────────────────────────────────────────────────────┤
│  Skill 运行时                                               │
│  ┌─────────────┐    ┌─────────────┐                      │
│  │  RAG 匹配    │───▶│ Agent 注入   │                      │
│  │ (description)│    │ SystemPrompt │                      │
│  └─────────────┘    └─────────────┘                      │
├─────────────────────────────────────────────────────────────┤
│  Skill 执行层                                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              tool-registry                             ││
│  │   scripts/ → 注册为 Agent Tool → LangGraph 执行        ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 11.3 数据模型

```sql
-- Skill 元数据表
CREATE TABLE skill (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    tenant_id BIGINT NOT NULL,
    name VARCHAR(64) NOT NULL,
    description TEXT NOT NULL,  -- 用于 RAG 匹配
    file_path VARCHAR(255) NOT NULL,  -- MinIO 中的 SKILL.md 路径
    enabled BOOLEAN DEFAULT TRUE,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_tenant_name (tenant_id, name),
    INDEX idx_description_tenant (tenant_id, description(100))
);

-- Skill 脚本文件表
CREATE TABLE skill_script (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    skill_id BIGINT NOT NULL,
    script_name VARCHAR(128) NOT NULL,
    script_type VARCHAR(16) NOT NULL,  -- python, bash
    file_path VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (skill_id) REFERENCES skill(id) ON DELETE CASCADE
);
```

### 11.4 触发流程

```
用户输入: "帮我查一下天气"
    ↓
Agent 分析意图 (LLM)
    ↓
RAG 检索 Skill (匹配 description)
    ↓
匹配到 "weather-query" Skill
    ↓
加载 SKILL.md 内容
    ↓
注入到 Agent System Prompt
    ↓
执行 Skill (调用 tool-registry 中的天气工具)
    ↓
返回结果
```

### 11.5 配置项

```yaml
nexus:
  agent-config:
    skill:
      enabled: true
      storage:
        minio:
          bucket: skills
      matching:
        top-k: 3
        threshold: 0.7
```


---

## 优化历史

### v2 优化（2026-03-17）

详见 [OPTIMIZATION_PLAN.md](./OPTIMIZATION_PLAN.md)

**P0 关键修复：**
1. ✅ Knowledge → Embed Worker 消息链补全（RabbitMQ）
2. ✅ Gateway JWT 黑名单校验（Redis 联查 `nexus:blacklist:{jti}`）
3. ✅ Agent Engine Tool Calling 节点（LangGraph 条件路由循环）

**P1 安全合规：**
4. ✅ Gateway 路由补全（5 → 12 条）
5. ✅ rag-service 端口冲突修复（8003 → 8013）
6. ✅ 敏感配置环境变量化 + `.env.example`

**P2 工程化：**
7. ✅ Docker Compose 全量编排（19 服务）
8. ✅ 补充测试（embed-worker / sandbox / gateway 黑名单 / tool calling）
9. ✅ 架构文档同步更新

### v3 优化（2026-03-17）

**Nacos + Sentinel 基础设施：**
1. ✅ Nacos 服务注册发现 — 8 个 Java 服务全部注册，Gateway lb:// 动态路由
2. ✅ Sentinel 限流熔断 — SentinelConfig 4 分组 12 规则 + 通用降级处理器

**代码质量提升：**
3. ✅ LLM Proxy 客户端连接池复用（ClientPool）
4. ✅ TokenStats Redis 持久化（重启不丢失 + 内存降级）
5. ✅ Memory Service 向量存储迁移 ChromaDB（替代 MySQL TEXT 字段）
6. ✅ Knowledge parseChunkConfigInt 改用 Jackson ObjectMapper
