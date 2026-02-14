# NexusAgent 架构设计文档

> 基于技术调研论的最终技术选型与各层设计

---

## 1. 系统架构总览

```
┌────────────────────────────────────────────────────────────────────────┐
│                           接入层 (Clients)                                  │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐             │
│   │ WebChat  │   │   QQ    │   │  飞书    │   │ REST API │             │
│   │  (Vue3)  │   │(OneBot) │   │   SDK    │   │ (第三方) │             │
│   └──────────┘   └──────────┘   └──────────┘   └──────────┘             │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    Spring Cloud Gateway (Port 8080)                         │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐                          │
│   │ JWT 认证  │   │ Tenant ID │   │  限流     │                          │
│   │ (Auth)   │   │  注入     │   │(Sentinel)│                          │
│   └──────────┘   └──────────┘   └──────────┘                          │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          Java 微服务层                                      │
│   ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐            │
│   │  Auth  │  │ Tenant │  │Session │  │Knowledge│  │  MCP   │            │
│   │ 认证服务│  │租户服务│  │会话服务│  │知识库服务│  │ Manager │            │
│   └────────┘  └────────┘  └────────┘  └────────┘  └────────┘            │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │                    Nexus Platform (WebChat + QQ)               │     │
│   │  ┌────────────────┐    ┌────────────────┐                │     │
│   │  │ WebSocket Handler│    │  QQ Adapter    │                │     │
│   │  │  (流式直连)      │    │  (MQ 异步)    │                │     │
│   │  └────────────────┘    └────────────────┘                │     │
│   └──────────────────────────────────────────────────────────────┘     │
│                                                                     │
│                        Nacos (服务注册与配置)                                │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          Python AI 服务层                                   │
│   ┌──────────────────────────────────────────────────────────────┐   │
│   │                    Agent Engine (LangGraph)                     │   │
│   │   ┌────────────┐  ┌────────────┐  ┌────────────────────┐     │   │
│   │   │ ToolManager│  │LoopController│  │ Followup Queue   │     │   │
│   │   │ (工具管理) │  │ (最大30次) │  │   (消息注入)     │     │   │
│   │   └────────────┘  └────────────┘  └────────────────────┘     │   │
│   └──────────────────────────────────────────────────────────────┘   │
│   ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐     │
│   │ LLM Proxy │  │Tool Registry│  │  Memory  │  │   RAG    │     │
│   │ (LLM调用)│  │ (工具执行) │  │ (会话记忆)│  │ (知识检索)│     │
│   └───────────┘  └───────────┘  └───────────┘  └───────────┘     │
│                                                                     │
│                        Nacos (服务注册)                                      │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          基础设层                                              │
│   ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐         │
│   │ MySQL 8│  │ Redis  │  │ Milvus │  │RabbitMQ│  │ MinIO  │         │
│   │(租户数据)│  │(缓存/会话)│  │(向量库)│  │(消息队列)│  │(文件存储)│         │
│   └────────┘  └────────┘  └────────┘  └────────┘  └────────┘         │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心模块设计

### 2.1 Agent Engine

Agent Engine 是系统的核心 AI 引擎，基于 LangGraph 实现。

#### 2.1.1 工具系统

**工具来源**：
| 来源 | 说明 | 权限控制 |
|------|------|----------|
| 内置工具 (BUILTIN) | calculator, web_search, sandbox_execute | 所有用户可见 |
| MCP Server (MCP) | 用户配置的外部 MCP Server | 按 Agent 绑定 |
| 自定义工具 (CUSTOM) | 租户自定义工具 | 按角色权限 |

**MCP Server 配置格式**：
```json
// SSE 模式
{
    "transport": "sse",
    "url": "https://mcp.example.com/sse",
    "headers": {"Authorization": "Bearer xxx"},
    "timeout": 30
}

// Streamable HTTP 模式
{
    "transport": "streamable_http",
    "url": "https://mcp.example.com/mcp",
    "headers": {"Authorization": "Bearer xxx"}
}
```

#### 2.1.2 Agent Loop 控制

- **最大循环次数**：30 次
- **强制输出**：到达上限后强制得到最终输出
- **强制输出 Prompt**：
```
你已达到最大工具调用次数（30次）。
请基于之前的分析和工具调用结果，直接回答用户的问题。
不要调用任何新工具，给出最终答案。
```

#### 2.1.3 Followup 队列

用户可以在 Agent 执行过程中注入新消息：
- 消息存储在 Redis 队列中
- 每次工具调用后检查队列
- 注入消息附加在 tool message 后面
- 按顺序排队，统一注入到 prompt

#### 2.1.4 会话控制

| 功能 | 说明 |
|------|------|
| 停止 | 流式/非流式都能中途停止 |
| 中断机制 | Redis flag + NodeInterrupt |

### 2.2 MCP Manager

MCP Server 管理服务（Java）：

| 功能 | 说明 |
|------|------|
| CRUD | MCP Server 创建/更新/删除 |
| 绑定 | 将 MCP Server 绑定到 Agent |
| 测试连接 | 验证 MCP Server 可用性 |
| 限制 | 每租户最多 100 个 MCP Server |

### 2.3 权限系统

**两次鉴权**：
1. **Agent 端**：快速过滤，减少 LLM token 消耗
2. **微服务端**：安全兜底，防止绕过

**权限模型**：
- 角色级别权限（role_tool_permission）
- Agent-MCP 绑定（agent_mcp_binding）

### 2.4 审计日志

所有租户相关操作都记录审计日志：
- 用户操作（创建/更新/删除）
- MCP Server 操作
- 工具执行记录

---

## 3. 数据流设计

### 3.1 WebChat 流式链路（直接 HTTP）

```
WebSocket → WebChatWebSocketHandler → AgentService → HTTP SSE → agent-engine
                                    ↓ 逐 token 推送
                                 WebSocket 客户端
```

### 3.2 QQ Bot 非流式链路（MQ 异步）

```
QQ 消息 → platform → MQ inbound 队列
                         ↓
                agent-engine 消费 → 非流式调用 → MQ outbound 队列
                         ↓
                platform 消费 → QQ API
```

### 3.3 工具调用链路

```
Agent (LLM 返回 tool_call)
         ↓
ToolManager.check_permission() → 第一次鉴权
         ↓
Tool-Registry / MCP Executor → 第二次鉴权
         ↓
执行工具 + 记录审计日志
```

---

## 4. 数据库设计

### 4.1 新增表

| 表名 | 说明 |
|------|------|
| mcp_server | MCP Server 配置 |
| agent_mcp_binding | Agent-MCP 绑定 |
| role_tool_permission | 角色-工具权限 |
| audit_log | 审计日志 |
| tool_execution_log | 工具调用记录 |
| mcp_execution_log | MCP 调用记录 |

### 4.2 Schema

详见 `sql/V2__mcp_tools_audit.sql`

---

## 5. API 设计

### 5.1 MCP Server

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/mcp/servers | GET | 列表 |
| /api/mcp/servers | POST | 创建 |
| /api/mcp/servers/{id} | PUT | 更新 |
| /api/mcp/servers/{id} | DELETE | 删除 |
| /api/mcp/servers/{id}/test | POST | 测试连接 |

### 5.2 Agent-MCP 绑定

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/agent/{id}/mcp | GET | 获取绑定列表 |
| /api/agent/{id}/mcp/bind | POST | 绑定 |
| /api/agent/{id}/mcp/{mcpId} | DELETE | 解绑 |

### 5.3 角色权限

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/role/{id}/tools | GET | 获取权限 |
| /api/role/{id}/tools | POST | 设置权限 |

---

## 6. Nacos 服务注册

所有 Python 服务都通过 Nacos 进行服务发现：

| 服务 | 服务名 | 端口 |
|------|--------|------|
| nexus-agent-engine | nexus-agent-engine | 8001 |
| nexus-llm-proxy | nexus-llm-proxy | 8010 |
| nexus-tool-registry | nexus-tool-registry | 8011 |
| nexus-memory-service | nexus-memory-service | 8012 |
| nexus-rag-service | nexus-rag-service | 8013 |
| nexus-sandbox-service | nexus-sandbox-service | 8020 |

---

## 7. 启动命令

```bash
# 启动所有服务
docker compose up -d

# 单独启动 Python 服务
cd python-services/agent-engine
pip install -r requirements.txt
python main.py
```

---

## 8. 环境变量

### 8.1 Python 服务

| 变量 | 说明 | 默认值 |
|------|------|--------|
| NACOS_ENABLED | 启用 Nacos | false |
| NACOS_SERVER | Nacos 地址 | 127.0.0.1:8848 |
| NACOS_SERVICE_NAME | 服务名 | - |
| REDIS_HOST | Redis 地址 | 127.0.0.1 |
| MYSQL_HOST | MySQL 地址 | 127.0.0.1 |

### 8.2 MCP Server

| 配置项 | 说明 |
|--------|------|
| transport | sse / streamable_http |
| url | MCP Server 地址 |
| headers | 认证头 |
| timeout | 超时秒数 |

---

## 9. 待实现功能

- [ ] MCP Server 实际连接测试
- [ ] MCP 工具列表获取
- [ ] 工具执行频率限制
- [ ] Rerank 优化
- [ ] 多模态支持
