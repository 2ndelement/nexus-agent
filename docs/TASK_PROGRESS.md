# NexusAgent 任务进度追踪

## 当前阶段
**Phase 0: 项目初始化** ✅ 已完成

---

## 已完成

- [x] 项目目录结构初始化
- [x] Git 仓库初始化
- [x] 技术选型确认 (Java + Python 双语言)
- [x] 技术调研：LangGraph 多租户隔离
- [x] 技术调研：Milvus BM25 + RRF 混合搜索
- [x] 技术调研：Spring Cloud Gateway 多租户 RBAC
- [x] 技术调研：Java ↔ Python 微服务通信
- [x] 生成 DESIGN_DECISIONS.md
- [x] 生成 ARCHITECTURE.md

---

## 进行中
- [~] 搭建 Docker 基础环境

---

## 待办

### Phase 1: 核心框架搭建 (重点)

#### 1.1 Docker 基础环境搭建
- [ ] 编写 docker-compose.yml (MySQL, Redis, Milvus, RabbitMQ, MinIO)
- [ ] 编写各服务 Dockerfile
- [ ] 配置 Nacos (服务注册与配置中心)
- [ ] 验证基础服务连通性

#### 1.2 Java 后端 - 认证服务
- [ ] 创建 nexus-auth 模块 (Spring Boot 3)
- [ ] 实现用户登录/注册 API
- [ ] 实现 JWT 签发与验证
- [ ] 集成 Redis 存储 Token
- [ ] 编写单元测试

#### 1.3 Java 后端 - 网关服务
- [ ] 创建 nexus-gateway 模块 (Spring Cloud Gateway)
- [ ] 实现 JWT 验证 Filter
- [ ] 实现 TenantContext 注入
- [ ] 配置路由规则
- [ ] 配置限流 (Sentinel)

#### 1.4 Java 后端 - 租户服务
- [ ] 创建 nexus-tenant 模块
- [ ] 实现租户 CRUD API
- [ ] 实现租户用户管理 API
- [ ] 集成 MyBatis-Plus
- [ ] 编写数据库脚本

#### 1.5 Python 后端 - Agent 引擎基础
- [ ] 创建 agent-engine 项目结构
- [ ] 配置 FastAPI 基础框架
- [ ] 实现 LangGraph 基础 Agent
- [ ] 配置 PostgreSQL checkpointer
- [ ] 实现流式输出 (SSE)

#### 1.6 公共依赖
- [ ] 创建 nexus-common 公共模块
- [ ] 定义统一 API 响应结构
- [ ] 定义异常处理
- [ ] 编写 gRPC 接口定义 (.proto)

### Phase 2: 核心功能实现

#### 2.1 会话服务
- [ ] 创建 nexus-session 模块
- [ ] 实现对话创建/查询 API
- [ ] 集成 Redis 会话缓存
- [ ] 消息持久化

#### 2.2 RAG 服务
- [ ] 创建 rag-service 项目
- [ ] 实现 Milvus 混合检索
- [ ] 实现文档上传与向量化
- [ ] 实现 BGE-M3 embedding

#### 2.3 LLM 代理
- [ ] 创建 llm-proxy 项目
- [ ] 实现多模型切换 (OpenAI/Claude/Ollama)
- [ ] 实现 Token 统计与计费

#### 2.4 工具注册
- [ ] 创建 tool-registry 项目
- [ ] 实现内置工具 (Web Search, Calculator)
- [ ] 实现工具执行沙箱

### Phase 3: 平台功能

#### 3.1 知识库服务
- [ ] 创建 nexus-knowledge 模块
- [ ] 实现文档管理 API
- [ ] 实现分片配置
- [ ] 实现知识库权限

#### 3.2 Agent 配置服务
- [ ] 创建 nexus-agent-config 模块
- [ ] 实现 Agent 模板管理
- [ ] 实现 Prompt 配置
- [ ] 实现工具绑定

#### 3.3 平台适配服务
- [ ] 创建 nexus-platform 模块
- [ ] 实现 WebChat 适配器
- [ ] 实现 QQ (OneBot) 适配器
- [ ] 实现飞书适配器

### Phase 4: 高级功能

#### 4.1 多 Agent 协同
- [ ] 实现 Supervisor Agent
- [ ] 实现 Agent 通信协议
- [ ] 实现任务编排

#### 4.2 计费服务
- [ ] 创建 nexus-billing 模块
- [ ] 实现配额管理
- [ ] 实现使用统计
- [ ] 实现告警通知

#### 4.3 监控与运维
- [ ] 集成 Prometheus
- [ ] 配置 Grafana 仪表盘
- [ ] 配置日志收集 (ELK)
- [ ] 配置链路追踪

---

## 技术决策记录

| 日期 | 决策项 | 最终方案 | 备注 |
|------|--------|----------|------|
| 2026-03-17 | LangGraph 多租户 | PostgreSQL + 命名空间隔离 | AsyncPostgresSaver |
| 2026-03-17 | RAG 混合搜索 | Milvus 原生 RRF | BGE-M3 + BM25 |
| 2026-03-17 | 多租户 RBAC | JWT + ThreadLocal + Redis | key 必须含 tenant |
| 2026-03-17 | 通信协议 | gRPC + SSE | 服务间 / 流式输出 |
| 2026-03-17 | 数据隔离 | 行级 + metadata filter | MySQL + Milvus |

---

## 里程碑

| 阶段 | 目标 | 预计完成 |
|------|------|----------|
| Phase 0 | 项目初始化 + 技术调研 | 2026-03-17 ✅ |
| Phase 1 | 核心框架搭建 | 2026-03-24 |
| Phase 2 | 核心功能实现 | 2026-04-07 |
| Phase 3 | 平台功能 | 2026-04-21 |
| Phase 4 | 高级功能 | 2026-05-05 |

---

## 子任务详情 (Phase 1)

### Task 1.1: Docker 基础环境
```
验收标准:
- docker-compose up 成功启动所有基础服务
- 各服务端口可访问
- Nacos 可正常注册服务
```

### Task 1.2: 认证服务 (nexus-auth)
```
验收标准:
- 用户可注册/登录
- JWT Token 正常签发与验证
- Token 存储到 Redis
```

### Task 1.3: 网关服务 (nexus-gateway)
```
验收标准:
- 拦截请求验证 JWT
- 正确提取并注入 Tenant ID
- 路由到各微服务
```

### Task 1.4: 租户服务 (nexus-tenant)
```
验收标准:
- 可创建/查询租户
- 可管理租户用户
- 具备完整的 CRUD API
```

### Task 1.5: Python Agent 引擎
```
验收标准:
- FastAPI 服务启动
- LangGraph Agent 可执行
- 支持流式输出 (SSE)
- PostgreSQL checkpointer 持久化
```

### Task 1.6: gRPC 接口定义
```
验收标准:
- 定义 AgentService proto 文件
- 生成 Java/Python 代码
- 实现简单的 gRPC 通信
```

---

*持续更新中...*
