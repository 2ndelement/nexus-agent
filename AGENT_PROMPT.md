# NexusAgent 项目启动 Prompt
## 项目概述

**NexusAgent** — 面向企业私有化部署的多租户 AI Agent 平台

目标：让企业内多用户可以使用同一个 AI 助手，支持 WebChat、QQ、飞书等多平台接入，实现多租户权限隔离、Agent 编排、RAG 知识库、多 Agent 协同等功能。

简历描述：
> 个人主导 | Spring Boot · Spring Cloud · MySQL · Redis · Milvus · RabbitMQ · Agent
> 面向企业私有化部署的 Agent 平台，支持多租户隔离，实现工具编排、记忆管理与多 Agent 协同。
> 设计 RBAC+Token 多租户权限模型，同一租户共享 Agent，不同租户数据与配额完全隔离；
> Milvus 向量检索 + BM25 混合排序 RAG 知识库；

---

## 📌 上下文背景

你正在和用户（2ndElement）一起实现这个项目。用户是后端开发，目标是面试造火箭、工作拧螺丝，需要一个可以在面试中讲清楚、有技术深度的完整项目。

当前进度：**项目规划阶段**，尚未开始编码。

---

## 🔧 工具链（已就绪）

| 工具 | 状态 | 使用方式 |
|------|------|----------|
| **Claude Code** (`claude`) | ✅ 已安装 | `/root/.local/bin/claude`，已配置 API Key + Base URL（Copilot Hub） |
| **tmux** | ✅ 可用 | 启动命令见下方 |
| **Git** | ✅ 可用 | v2.47.3 |
| **Tavily 搜索** | ✅ 可用 | `web_search_tavily` 函数 |
| **定时任务** | ✅ 可用 | `create_future_task` 创建唤醒任务 |
| **AstrBot 知识库** | ✅ 可用 | `astr_kb_search` 搜索内部知识 |

### Claude Code 启动方式

```bash
# 启动 Claude Code (bypass 模式，无需每次确认)
tmux new-session -d -s claude-code -x 220 -y 50
tmux send-keys -t claude-code "export PATH=\$PATH:/root/.local/bin && IS_SANDBOX=1 claude --dangerously-skip-permissions" Enter

# 等待 6 秒后检查，底部出现 "bypass permissions on" 即就绪
sleep 6
tmux capture-pane -t claude-code -p | tail -10
```

### 给 Claude Code 发送任务

```bash
# 先发送任务描述
tmux send-keys -t claude-code -l -- "你的任务描述"
sleep 0.3
# 按回车执行
tmux send-keys -t claude-code Enter

# 查看结果
sleep 15
tmux capture-pane -t claude-code -p -S -200 | tail -30
```

---

## 🏗️ 当前已确定的技术选型

### 架构：Java + Python 双语言混合

| 职责 | 语言 | 理由 |
|------|------|------|
| 网关、权限、会话、消息路由、计量计费 | Java (Spring Cloud) | 高并发、成熟微服务生态、RBAC 场景 Java 更强 |
| Agent 执行引擎、RAG、Tool 调用、LLM 调用 | Python (FastAPI) | LangGraph/LangChain 生态、AI 库最完善 |
| 消息总线（解耦） | RabbitMQ | 异步解耦，各自扩容 |

### 核心技术栈（草稿）

```
接入层：    Vue3 (WebChat) + QQ (OneBot v11) + 飞书
网关：      Spring Cloud Gateway + Sentinel
服务治理：  Nacos
Java：     Spring Boot 3 + MyBatis-Plus
Python：   FastAPI + LangGraph + LangChain
向量库：    Milvus + BM25 + RRF 混合排序
关系库：    MySQL 8
缓存：      Redis
对象存储：  MinIO
监控：      Prometheus + Grafana
```

---

## ⚠️ 重要：设计待完善

以下内容需要通过**搜索研究和讨论**来最终确定：

### 1. LangGraph 多租户 Agent 隔离方案
- 每个租户的 graph state 如何隔离？
- checkpoint 持久化策略？
- 参考：LangGraph 官方 multi-tenant 最佳实践

### 2. Java ↔ Python 通信方式
- 同步调用选 gRPC 还是 REST？
- 流式输出 SSE 如何从 Python 穿透到前端？
- RabbitMQ 在 AI 推理任务中的背压处理

### 3. RAG 混合检索细节
- BM25 用 Elasticsearch 还是内存实现（Rank BM25）？
- Embedding 模型选型（BGE vs OpenAI）？
- RRF 参数调优策略

### 4. 多租户数据隔离策略
- MySQL：行级隔离 vs Schema 隔离的临界点
- Milvus：Collection 隔离 vs metadata filter 哪个性能好？

### 5. 参照开源项目
- Dify / FastGPT 的多租户架构
- LangChain Agents 官方多 Agent 示例
- Coze / BPM 商业产品设计

---

## 📁 项目目录结构（规划中）

```
/AstrBot/data/workspace/nexus-agent/
├── docs/
│   ├── ARCHITECTURE.md          # 架构设计文档
│   ├── TASK_PROGRESS.md         # 任务进度追踪（核心！）
│   ├── DESIGN_DECISIONS.md      # 技术决策记录
│   └── api/
├── nexus-gateway/               # Spring Cloud Gateway
├── nexus-auth/                  # 认证服务
├── nexus-tenant/                # 租户服务
├── nexus-session/               # 会话服务
├── nexus-knowledge/             # 知识库服务
├── nexus-agent-config/          # Agent 配置服务
├── nexus-platform/              # 平台适配服务
├── nexus-billing/               # 计量计费服务
├── nexus-common/                # 公共依赖
├── python-services/
│   ├── agent-engine/            # LangGraph 引擎
│   ├── rag-service/             # RAG 检索
│   ├── tool-registry/           # 工具注册
│   ├── memory-service/          # 记忆管理
│   ├── llm-proxy/               # LLM 代理
│   └── embed-worker/            # 向量化 Worker
└── docker-compose.yml           # 本地基础设施
```

---

## 🚀 你的任务（Phase 0：项目初始化）

### 步骤 1：创建项目结构
1. 在 `/AstrBot/data/workspace/nexus-agent/` 下初始化项目
2. 创建 `docs/` 目录和 `TASK_PROGRESS.md`
3. 提交 git 初始 commit

### 步骤 2：技术预研（必须先做！）
用 Tavily 搜索以下问题，记录到 `docs/DESIGN_DECISIONS.md`：

1. **LangGraph multi-tenant** — 搜索 "LangGraph multi-tenant isolation production best practice"
2. **RAG hybrid search RRF** — 搜索 "Milvus BM25 RRF hybrid search implementation 2024"
3. **Spring Cloud multi-tenant** — 搜索 "Spring Cloud Gateway multi-tenant tenant isolation RBAC"
4. **Java Python microservice AI** — 搜索 "Java Python microservices AI agent LangChain communication"

### 步骤 3：产出设计文档
根据搜索结果，更新 `docs/ARCHITECTURE.md` 和 `docs/DESIGN_DECISIONS.md`，产出最终技术选型方案。

### 步骤 4：任务拆分
基于确定的设计，将 Phase 1（核心功能）拆成可执行的子任务，写入 `TASK_PROGRESS.md`。

---

## 📋 任务进度文件格式（TASK_PROGRESS.md）

```markdown
# NexusAgent 任务进度

## 当前阶段
[Phase 0: 项目初始化 / Phase 1: 核心架构]

## 已完成
- [x] 项目目录初始化
- [x] 技术选型确认 (Java + Python 双语言)

## 进行中
- [~] 技术预研：LangGraph 多租户隔离方案

## 待办
- [ ] 产出 ARCHITECTURE.md
- [ ] 产出 DESIGN_DECISIONS.md
- [ ] 搭建 Docker 基础设施
- [ ] 实现 Phase 1: 认证 + 租户 + 网关

## 技术决策记录
| 日期 | 问题 | 方案 | 备注 |
|------|------|------|------|
| 2026-03-17 | LangGraph 多租户隔离 | 待搜索确定 | |
```

---

## ⚠️ 注意事项

1. **不要直接开始编码**：先把设计确定下来，避免返工
2. **每完成一个搜索任务**：更新 `TASK_PROGRESS.md`
3. **重要决策**：必须记录到 `DESIGN_DECISIONS.md`，包括问题、方案、理由、备选
4. **防止 ReAct loop 断掉**：长任务执行前创建 `create_future_task` 定时唤醒
5. **进度汇报**：每个阶段完成后主动向用户汇报

---

## 📞 与用户沟通

- 用户 ID：2781372804
- 昵称：2ndElement
- 沟通方式：通过 AstrBot 消息
- 汇报时机：设计文档完成后、每个阶段开始/结束时

---

启动吧！先从创建项目结构和开始技术预研开始。🚀
