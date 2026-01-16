# NexusAgent 架构设计文档

> 基于技术调研结论的最终技术选型与各层设计

---

## 1. 系统架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           接入层 (Clients)                                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────┐   │
│  │ WebChat │  │   QQ    │  │ 飞书    │  │Discord  │  │  REST API   │   │
│  │ (Vue3)  │  │(OneBot) │  │  SDK    │  │   SDK   │  │  (第三方)    │   │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └──────┬──────┘   │
└───────┼────────────┼────────────┼────────────┼──────────────┼───────────┘
        │            │            │            │              │
        └────────────┴────────────┴────────────┴──────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Spring Cloud Gateway (Port 8080)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │ JWT 认证     │  │ Tenant ID    │  │ 限流         │                   │
│  │ (Auth)      │  │ 提取注入     │  │ (Sentinel)  │                   │
│  └──────────────┘  └──────────────┘  └──────────────┘                   │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Java 微服务层                                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────┐  │
│  │  Auth   │  │ Tenant  │  │Session  │  │Knowledge │  │   Config   │  │
│  │ 认证服务 │  │租户服务 │  │会话服务 │  │知识库服务 │  │Agent配置   │  │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └──────┬──────┘  │
│       │            │            │            │               │            │
│       └────────────┴────────────┴────────────┴───────────────┘            │
│                              │                                             │
│                    Nacos (服务注册与配置)                                   │
└──────────────────────────────┼─────────────────────────────────────────────┘
                               │ (gRPC/REST)
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Python AI 服务层                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ Agent Engine│  │  LLM Proxy  │  │ RAG Service │  │Memory Service│     │
│  │ (LangGraph) │  │  (LLM调用)  │  │ (混合检索)  │  │ (会话记忆)   │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │
│         │                 │                  │                 │            │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐                 │
│  │Tool Registry│  │ Embed Worker │  │  Milvus    │                 │
│  │ (工具注册)  │  │ (向量嵌入)   │  │ (向量库)   │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                              (消息队列)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          基础设施层                                         │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌─────────┐  ┌──────────┐        │
│  │ MySQL 8│  │ Redis  │  │ Milvus │  │RabbitMQ │  │  MinIO   │        │
│  │(租户数据)│  │(缓存/会话)│  │(向量库)│  │(消息队列)│  │(文件存储)│        │
│  └────────┘  └────────┘  └────────┘  └─────────┘  └──────────┘        │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │            Prometheus + Grafana (监控)                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
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
| 类型 | 有期限 | 用途 |
|------|--------|------|
| Access Token | 2 小时 | API 调用 |
| Refresh Token | 7 天 | 刷新 Access Token |

---

### 2.2 租户服务 (Tenant Service)

**职责：** 租户 CRUD + 成员管理 + 多租户隔离

**技术栈：** Spring Boot 3 + MyBatis-Plus + MySQL

**隔离策略：**
- 数据隔离：每个租户独立数据库或表前缀
- 认证隔离：JWT 中携带 tenant_id
- 资源隔离：Agent Engine 使用 thread_id = `{tenant_id}:{conversation_id}`

---

### 2.3 会话服务 (Session Service)

**职责：** 会话 CRUD、消息管理、上下文管理

**核心 API：**
```java
POST /api/session/conversations     // 创建会话
GET  /api/session/conversations     // 列表查询
GET  /api/session/conversations/{id} // 获取会话详情
POST /api/session/messages          // 发送消息
```

---

### 2.4 Agent 引擎 (Agent Engine)

**职责：** LangGraph Agent 编排、LLM 调用、Tool 执行

**技术栈：** Python + LangGraph + FastAPI + MySQL Checkpoint

**核心特性：**
- 状态持久化：AIOMySQLSaver 支持多租户隔离
- 流式输出：SSE (Server-Sent Events)
- Tool 调用链：自动识别并执行注册的工具

**架构：**
```python
# LangGraph 图定义
builder = StateGraph(AgentState)
builder.add_node("call_llm", call_llm_node)
builder.add_edge(START, "call_llm")
builder.add_edge("call_llm", END)
```

**端口：** 8001

---

### 2.5 LLM 代理 (LLM Proxy)

**职责：** 统一 LLM 调用、多模型路由、Token 统计

**技术栈：** Python + FastAPI + OpenAI SDK

**核心特性：**
- OpenAI 协议兼容
- 多模型路由：MiniMax / Claude / OpenAI / Azure OpenAI
- Token 用量统计与配额控制

**端口：** 8010

---

### 2.6 RAG 服务 (RAG Service)

**职责：** 知识库管理、文档处理、混合检索

**技术栈：** Python + FastAPI + Milvus + BM25

**检索流程：**
1. 用户查询 → 向量化 (embedding)
2. 向量检索 (Milvus) + 关键词检索 (BM25)
3. RRF 融合排序
4. 返回 top-k 结果

**端口：** 8003

---

### 2.7 知识库服务 (Knowledge Service)

**职责：** 知识库 CRUD、文档上传、文本提取、分块

**技术栈：** Java + Spring Boot + MinIO + PDFBox

**支持格式：** PDF, DOCX, TXT, Markdown

---

### 2.8 工具注册中心 (Tool Registry)

**职责：** 工具注册、工具发现、工具调用

**技术栈：** Python + FastAPI

**端口：** 8011

---

### 2.9 记忆服务 (Memory Service)

**职责：** 会话记忆存储与检索

**技术栈：** Python + FastAPI + MySQL

**端口：** 8012

---

### 2.10 Agent 配置服务 (Agent Config Service)

**职责：** Agent 配置管理、Skill 系统

**技术栈：** Java + Spring Boot

**核心功能：**
- Agent 配置 CRUD
- Skill 技能定义与管理
- 预置 Agent 模板

**端口：** 8006

---

## 3. 网关设计 (Gateway)

**端口：** 8080

**核心功能：**
1. **JWT 认证：** 验证 Token 有效性，提取用户信息
2. **租户注入：** 将 tenant_id 注入到请求头
3. **路由转发：** 根据路径规则分发到后端服务
4. **限流保护：** Sentinel 限流

**路由规则：**
```
/api/auth/*        → auth-service:8005
/api/tenant/*      → tenant-service:8002
/api/session/*     → session-service:8004
/api/knowledge/*   → knowledge-service:8007
/api/agent/*       → agent-engine:8001
/api/billing/*     → billing-service:8009
/api/config/*      → agent-config:8006
```

---

## 4. 消息队列设计

**中间件：** RabbitMQ

**用途：**
- 异步任务：文档处理、embedding 生成
- 事件通知：Token 刷新、会话状态变更
- 流量削峰：高并发场景下的请求缓冲

---

## 5. 服务端口汇总

| 服务 | 端口 | 协议 | 说明 |
|------|------|------|------|
| Gateway | 8080 | HTTP | 统一入口 |
| Auth | 8005 | HTTP | 认证服务 |
| Tenant | 8002 | HTTP | 租户服务 |
| Session | 8004 | HTTP | 会话服务 |
| Knowledge | 8007 | HTTP | 知识库服务 |
| Agent Config | 8006 | HTTP | Agent 配置 |
| Billing | 8009 | HTTP | 计费服务 |
| Agent Engine | 8001 | HTTP | Agent 引擎 |
| LLM Proxy | 8010 | HTTP | LLM 代理 |
| RAG Service | 8003 | HTTP | RAG 服务 |
| Tool Registry | 8011 | HTTP | 工具注册 |
| Memory Service | 8012 | HTTP | 记忆服务 |

---

## 6. 技术栈总结

### Java 服务
- **框架：** Spring Boot 3 + Spring Cloud
- **ORM：** MyBatis-Plus
- **数据库：** MySQL 8
- **缓存：** Redis
- **消息队列：** RabbitMQ

### Python 服务
- **框架：** FastAPI
- **AI 框架：** LangChain / LangGraph
- **向量库：** Milvus
- **LLM：** OpenAI / MiniMax / Anthropic

### 前端
- **框架：** Vue 3
- **UI：** Tailwind CSS
- **状态管理：** Pinia

---

## 7. 部署架构

### 开发环境
- 所有服务本地运行
- MySQL/Redis/MinIO 使用 Docker

### 生产环境
- Kubernetes (K8s)
- 每个微服务独立部署
- MySQL/Redis/Milvus 使用云服务或集群

---

*文档版本：v1.0*
*最后更新：2026-03-17*

---

## 8. Embed Worker (embed-worker)

**职责：** 异步文档向量化 — 消费 RabbitMQ 消息 → 调用 SentenceTransformer → 写入 ChromaDB

**技术栈：** Python + aio-pika + chromadb + sentence-transformers

**消息队列：**
- 消费队列：`nexus.embed.tasks`
- 消息格式：tenant_id, kb_id, doc_id, chunks[]

**端口：** N/A（纯消费者）

---

## 9. Sandbox Service (sandbox-service)

**职责：** 隔离容器中执行任意代码（Python/Bash）

**技术栈：** Python + FastAPI + aiodocker (Docker)

**安全特性：**
- 网络隔离（容器无外网访问）
- 资源限制：内存 256MB，CPU 0.5 核
- 超时控制：最长 120 秒
- 容器级隔离，每次执行创建临时容器

**端口：** 8020

**核心 API：**
```python
POST /execute
{
    "code": "print('hello')",
    "language": "python",  # or "bash"
    "timeout": 30
}
```

**在 Tool Registry 中注册为 `sandbox_execute` 工具**

---

## 10. 服务端口汇总（更新版）

| 服务 | 端口 | 协议 |
|------|------|------|
| Gateway | 8080 | HTTP |
| Auth | 8005 | HTTP |
| Tenant | 8002 | HTTP |
| Session | 8004 | HTTP |
| Knowledge | 8007 | HTTP |
| Agent Config | 8006 | HTTP |
| Billing | 8009 | HTTP |
| Agent Engine | 8001 | HTTP |
| LLM Proxy | 8010 | HTTP |
| RAG Service | 8003 | HTTP |
| Tool Registry | 8011 | HTTP |
| Memory Service | 8012 | HTTP |
| Sandbox Service | 8020 | HTTP |
| Embed Worker | N/A | RabbitMQ |

---

*文档版本：v1.1*
*最后更新：2026-03-17*
