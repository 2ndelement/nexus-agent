# NexusAgent 开发进度

## Phase 1 - 基础设施 ✅
- [x] 项目目录结构初始化
- [x] Git 仓库初始化
- [x] 技术选型确认 (Java + Python 双语言)
- [x] 技术调研：LangGraph 多租户隔离
- [x] 技术调研：Milvus BM25 + RRF 混合搜索
- [x] 技术调研：Spring Cloud Gateway 多租户 RBAC
- [x] 技术调研：Java ↔ Python 微服务通信
- [x] 生成 DESIGN_DECISIONS.md
- [x] 生成 ARCHITECTURE.md

## Phase 2 - 核心功能 ✅
- [x] 创建 nexus-session 模块 - 已完成（36 tests）
- [x] 实现对话创建/查询 API - 已完成
- [x] 集成 Redis 会话缓存 - 已完成
- [x] 消息持久化 - 已完成
- [x] 完善 Milvus 混合检索 - 已完成
- [x] 实现文档上传与向量化 - 已完成
- [x] 实现 BGE-M3 embedding - 已完成
- [x] 创建 llm-proxy 项目 - 已完成（15 py files）
- [x] 实现多模型切换 (OpenAI/Claude/Ollama) - 已完成
- [x] 实现 Token 统计与计费 - 已完成
- [x] 创建 tool-registry 项目 - 已完成
- [x] 实现内置工具 (Web Search, Calculator) - 已完成
- [x] 实现工具执行沙箱 - 已完成
- [x] 创建 memory-service 项目 - 已完成
- [x] 实现会话记忆存储 - 已完成
- [x] 实现记忆检索 - 已完成

## Phase 3 - 平台适配器+Agent配置 ✅
- [x] 创建 webchat 模块 - 已完成
- [x] 实现 WebSocket 实时通信 - 已完成
- [x] 实现 HTTP API 接口 - 已完成
- [x] 创建 qq-bot 模块 - 已完成
- [x] 实现 WebSocket 长连接 - 已完成
- [x] 实现消息接收与发送 - 已完成
- [x] 实现事件处理 (群聊/私聊/频道) - 已完成
- [x] 创建 nexus-agent-config 模块 - 已完成
- [x] 实现 Agent 模板管理 - 已完成
- [x] 实现 Prompt 配置 - 已完成
- [x] 实现工具绑定 - 已完成
- [x] 设计 Skill 存储结构 (MySQL + MinIO) - 已完成
- [x] 实现 Skill 加载与注册 - 已完成
- [x] 实现 Skill 匹配 (RAG 向量检索 description) - 已完成
- [x] 实现 Skill 注入 (SKILL.md 内容注入 Agent System Prompt) - 已完成

## Phase 4 - 高级功能 ✅
- [x] 创建 nexus-knowledge 模块 - 已完成（41 tests）
- [x] 实现知识库 CRUD - 已完成
- [x] 实现文档管理 API - 已完成
- [x] 实现分片配置 - 已完成
- [x] 实现权限控制 - 已完成
- [x] 创建 nexus-billing 模块 - 已完成
- [x] 实现套餐/配额管理 - 已完成
- [x] 实现使用统计 - 已完成
- [x] 实现告警通知 - 已完成

## 联调测试 ⏳
- [ ] agent-engine 调用 nexus-session 保存消息
- [ ] agent-engine 调用 llm-proxy 处理 LLM 请求
- [ ] nexus-platform 接收消息 → agent-engine 处理 → 回复
- [ ] 完整链路：用户消息 → QQ/WebChat → nexus-platform → agent-engine → llm-proxy → 回复

## 已提交模块列表
| 模块 | 语言 | 测试 | 端口 |
|------|------|------|------|
| nexus-common | Java | 32 | - |
| nexus-auth | Java | - | - |
| nexus-gateway | Java | 17 | 8080 |
| nexus-tenant | Java | 7 | 8003 |
| nexus-session | Java | 36 | 8004 |
| nexus-platform | Java | - | 8005 |
| nexus-agent-config | Java | 18 | 8006 |
| nexus-knowledge | Java | 41 | 8007 |
| nexus-billing | Java | - | 8008 |
| agent-engine | Python | 19 | 8090 |
| rag-service | Python | 55 | 8091 |
| llm-proxy | Python | 12 | 8010 |
| tool-registry | Python | - | 8011 |
| memory-service | Python | - | 8012 |


---

## 系统优化 — v2（2026-03-17）

基于全项目代码审查，识别并修复了 10 个优化项。

### 已完成

| # | 优化项 | 优先级 | 涉及模块 |
|---|--------|--------|----------|
| 1 | Knowledge → Embed Worker 消息链补全 | P0 | nexus-knowledge, EmbedTaskPublisher |
| 2 | Gateway JWT 黑名单校验 | P0 | nexus-gateway, AuthGlobalFilter |
| 3 | Agent Engine Tool Calling 节点 | P0 | agent-engine (nodes.py, graph.py) |
| 4 | Gateway 路由补全（5→12条） | P1 | nexus-gateway/application.yml |
| 5 | rag-service 端口冲突修复（8003→8013） | P1 | rag-service, agent-engine |
| 6 | 敏感配置环境变量化 | P1 | 6个Java服务yml, .env.example |
| 7 | Docker Compose 全量编排 | P2 | docker-compose.yml, Dockerfile.java |
| 8 | 补充测试 | P2 | 4个新测试文件 |
| 9 | 架构文档同步更新 | P2 | ARCHITECTURE.md |
| 10 | 优化计划文档 | P2 | OPTIMIZATION_PLAN.md |

### 新增文件

```
(new) .env.example                          — 环境变量模板
(new) docker-compose.yml                    — 19服务编排
(new) Dockerfile.java                       — Java通用多阶段构建
(new) nexus-knowledge/.../mq/EmbedTaskPublisher.java    — 向量化消息发布
(new) python-services/agent-engine/tests/test_tool_calling.py
(new) python-services/embed-worker/tests/test_consumer.py
(new) python-services/sandbox-service/tests/test_executor.py
(new) docs/OPTIMIZATION_PLAN.md             — 优化计划文档
```

### 修改文件

```
(mod) nexus-gateway/.../AuthGlobalFilter.java           — +黑名单校验
(mod) nexus-gateway/.../application.yml                 — +Redis配置, +7条路由
(mod) nexus-gateway/pom.xml                             — +spring-data-redis
(mod) nexus-gateway/.../AuthGlobalFilterTest.java       — +黑名单测试用例
(mod) nexus-knowledge/pom.xml                           — +spring-amqp
(mod) nexus-knowledge/.../application.yml               — +RabbitMQ配置
(mod) nexus-knowledge/.../DocumentServiceImpl.java      — +向量化消息发送
(mod) python-services/agent-engine/app/agent/nodes.py   — 重写(+tool calling)
(mod) python-services/agent-engine/app/agent/graph.py   — 重写(+条件路由)
(mod) python-services/agent-engine/app/config.py        — +服务地址配置
(mod) python-services/rag-service/app/config.py         — 端口8003→8013
(mod) nexus-auth/.../application.yml                    — 环境变量化
(mod) nexus-tenant/.../application.yml                  — 环境变量化
(mod) nexus-session/.../application.yml                 — 环境变量化
(mod) nexus-billing/.../application.yml                 — 环境变量化
(mod) nexus-agent-config/.../application.yml            — 环境变量化
(mod) docs/ARCHITECTURE.md                              — 全面更新
```


---

## v3 优化（2026-03-17）

| # | 优化项 | 涉及模块 |
|---|--------|----------|
| 11 | Nacos 服务注册发现 | 8个Java服务 pom+yml |
| 12 | Sentinel 限流熔断 | Gateway SentinelConfig + common FallbackHandler |
| 13 | LLM Proxy 客户端连接池 | llm-proxy/router.py ClientPool |
| 14 | TokenStats Redis 持久化 | llm-proxy/token_stats.py |
| 15 | Memory Service ChromaDB | memory-service/memory_service.py |
| 16 | parseChunkConfigInt | knowledge/DocumentServiceImpl.java |
