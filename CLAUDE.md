# CLAUDE.md - 开发指南

## 项目概述

NexusAgent 是一个基于 LangGraph 的 AI Agent 系统，支持多租户、多工具、多平台接入。

## 技术栈

- **Java**: Spring Boot 3 + Spring Cloud + Nacos
- **Python**: FastAPI + LangGraph + LangChain
- **数据库**: MySQL 8 + Redis + Milvus
- **消息队列**: RabbitMQ

## 目录结构

```
nexus-agent/
├── nexus-platform/          # Java: WebChat + QQ 适配器
├── nexus-gateway/          # Java: API Gateway
├── nexus-auth/             # Java: 认证服务
├── nexus-tenant/           # Java: 租户服务
├── nexus-session/          # Java: 会话服务
├── nexus-agent-config/     # Java: Agent 配置
├── nexus-knowledge/        # Java: 知识库
├── nexus-billing/          # Java: 计费
├── nexus-mcp-manager/      # Java: MCP Server 管理
├── python-services/
│   ├── agent-engine/      # Python: AI 核心引擎
│   ├── llm-proxy/        # Python: LLM 代理
│   ├── tool-registry/     # Python: 工具注册中心
│   ├── memory-service/    # Python: 记忆服务
│   ├── rag-service/       # Python: RAG 服务
│   └── sandbox-service/   # Python: 代码沙箱
├── sql/                   # 数据库 Schema
└── docker-compose.yml
```

## 开发规范

### Java 代码规范

- 使用 Lombok 简化代码
- 使用 MyBatis-Plus 操作数据库
- 使用 Nacos 进行服务发现
- 使用 Sentinel 进行限流熔断

### Python 代码规范

- 使用类型注解
- 使用 async/await 处理异步
- 使用 Pydantic 进行数据验证
- 使用日志记录关键操作

### Git 提交规范

```
feat: 新功能
fix: 修复
docs: 文档
refactor: 重构
test: 测试
chore: 构建/工具
```

## 数据库

### 表结构

| 表名 | 说明 |
|------|------|
| mcp_server | MCP Server 配置 |
| agent_mcp_binding | Agent-MCP 绑定 |
| role_tool_permission | 角色-工具权限 |
| audit_log | 审计日志 |
| tool_execution_log | 工具调用记录 |

详见 `sql/V2__mcp_tools_audit.sql`

## 工具系统

### 工具来源

1. **内置工具**: calculator, web_search, sandbox_execute
2. **MCP Server**: 用户配置的外部 MCP
3. **自定义工具**: 租户自定义工具

### 权限控制

两次鉴权：
1. Agent 端快速过滤
2. 微服务端安全兜底

## Agent 控制

### 停止对话

```python
# 发送停止信号
interrupt_controller.stop(conversation_id)
```

### Followup 消息

```python
# 添加到队列
followup_queue.add(FollowupMessage(...))
```

### 最大循环次数

默认 30 次，到达后强制输出。

## MCP Server

### 配置格式

```json
{
    "transport": "sse",
    "url": "https://mcp.example.com/sse",
    "headers": {"Authorization": "Bearer xxx"}
}
```

### 绑定到 Agent

通过 `agent-mcp-binding` 表关联。

## 测试

```bash
# Java
cd nexus-platform
mvn test

# Python
cd python-services/agent-engine
pytest
```

## 环境变量

| 变量 | 说明 |
|------|------|
| NACOS_ENABLED | 启用 Nacos |
| NACOS_SERVICE_NAME | 服务名 |
| REDIS_HOST | Redis 地址 |
| MYSQL_HOST | MySQL 地址 |
