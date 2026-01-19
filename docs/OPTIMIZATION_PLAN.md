# NexusAgent 优化计划

> 基于全项目代码审查的系统性优化方案
> 生成时间：2026-03-17
> 状态：✅ 全部完成

---

## 一、关键断裂链路（P0 — 必须修复）

### 1.1 Knowledge → Embed Worker 消息链断裂
- **问题**：`DocumentServiceImpl.upload()` 完成分片后只写了 MySQL `document_chunk` 表，但**没有向 RabbitMQ 发送消息通知 embed-worker**，向量化永远不会触发
- **修复**：在 knowledge-service 中引入 `spring-amqp`，上传完成后发送 `EmbedTask` 消息到 `nexus.embed.tasks` 队列
- **文件**：
  - `nexus-knowledge/pom.xml` — 添加 `spring-boot-starter-amqp`
  - `nexus-knowledge/src/main/resources/application.yml` — RabbitMQ 配置
  - 新增 `EmbedTaskPublisher.java` — 消息发布器
  - 修改 `DocumentServiceImpl.java` — 注入 Publisher，上传完成后发消息

### 1.2 Gateway JWT 黑名单校验缺失
- **问题**：Auth 服务 logout 时将 `jti` 加入 Redis 黑名单，但 Gateway `AuthGlobalFilter` **完全没有检查黑名单**，已登出的 Token 仍然有效
- **修复**：在 Gateway Filter 中解析 `jti`，查 Redis 黑名单
- **文件**：`AuthGlobalFilter.java`

### 1.3 Agent Engine 缺少 Tool Calling 节点
- **问题**：LangGraph 图只有 `START → call_llm → END`，**没有工具调用节点**，Agent 无法使用 calculator / web_search / sandbox 等已注册工具
- **修复**：增加 `tool_node` + 条件路由（LLM 返回 tool_calls → 执行工具 → 回到 LLM）
- **文件**：
  - `nodes.py` — 新增 `tool_call_node`
  - `graph.py` — 增加条件边

---

## 二、安全与合规（P1 — 高优先级）

### 2.1 Gateway 路由缺失多个服务
- **问题**：Gateway 只配置了 auth / tenant / session / agent / knowledge 五条路由，**缺少** billing(8009)、agent-config(8006)、tool-registry(8011)、memory(8012)、sandbox(8020)、platform(8005) 的路由
- **修复**：补全 Gateway 路由配置

### 2.2 Gateway 端口冲突
- **问题**：auth 配置为 8002，但 ARCHITECTURE 记录 auth=8005；platform 声明端口 8005 与 auth 冲突
- **修复**：统一端口分配，以实际 yml 为准，更新文档

### 2.3 敏感配置硬编码
- **问题**：JWT Secret、MySQL 密码均硬编码在 yml 中（仅部分使用了 `${ENV:default}` 占位符）
- **修复**：全部改为 `${ENV_VAR:default}` 形式，添加 `.env.example`

---

## 三、工程化与可运维（P2 — 重要）

### 3.1 缺少 Docker Compose
- **问题**：无 `docker-compose.yml`，12+ 个微服务 + 中间件无法一键启动
- **修复**：创建完整的 docker-compose.yml

### 3.2 缺少 Sentinel 限流
- **问题**：ARCHITECTURE 提到 Sentinel 限流，但**零配置零代码**
- **修复**：暂标记为文档规划项，不实际引入（避免过度设计）

### 3.3 缺少 Nacos 服务发现
- **问题**：所有服务间调用使用硬编码 `localhost:port`，无服务发现
- **修复**：暂保持现状（单机部署足够），在架构文档中标注为"Phase 2"

### 3.4 embed-worker / sandbox-service 缺少测试
- **修复**：补充单元测试

### 3.5 Token 统计仅内存存储
- **问题**：`llm-proxy` 的 `TokenStats` 使用内存，重启清零
- **修复**：标记为已知限制，后续可持久化到 Redis

---

## 四、代码质量（P3 — 改善）

### 4.1 Memory Service 向量存储在 MySQL TEXT 字段
- **问题**：384 维向量序列化为逗号分隔字符串存 MySQL TEXT，检索时全量加载到内存做余弦相似度
- **修复**：后续迁移到 ChromaDB（与 RAG 共用），当前标注限制

### 4.2 Knowledge Service JSON 解析用字符串截取
- **问题**：`parseChunkConfigInt()` 用 `indexOf` 手动解析 JSON
- **修复**：改用 Jackson ObjectMapper

### 4.3 LLM Proxy 每次请求新建 AsyncOpenAI 客户端
- **问题**：`_build_client()` 每次创建新实例，无连接池复用
- **修复**：引入 provider → client 缓存

---

## 执行优先级

| 序号 | 优化项 | 优先级 | 状态 |
|------|--------|--------|------|
| 1 | Knowledge→Embed 消息链 | P0 | ✅ 完成 |
| 2 | Gateway 黑名单校验 | P0 | ✅ 完成 |
| 3 | Agent Tool Calling | P0 | ✅ 完成 |
| 4 | Gateway 路由补全 | P1 | ✅ 完成 |
| 5 | 端口冲突修复 | P1 | ✅ 完成 |
| 6 | 敏感配置环境变量化 | P1 | ✅ 完成 |
| 7 | Docker Compose | P2 | ✅ 完成 |
| 8 | 补充测试 | P2 | ✅ 完成 |
| 9 | .env.example | P2 | ✅ 完成 |
| 10 | 架构文档更新 | P2 | ✅ 完成 |

---

*文档版本：v1.1（执行完成）*
*最后更新：2026-03-17*
