# NexusAgent — Claude Code 工作流规范

> 本文件是帕托莉（AI 助手）与 Claude Code（编码 Agent）之间的协作协议。
> 每个编码任务必须严格遵守：设计 → 评审 → 编码 → 测试 的闭环。

---

## 一、整体分工

| 角色 | 职责 |
|------|------|
| **帕托莉 (Orchestrator)** | 任务拆解、设计评审、质量把关、进度汇报 |
| **Claude Code (Coder)** | 具体编码实现、编写测试、执行测试 |
| **2ndElement (Owner)** | 需求确认、关键设计决策、最终验收 |

---

## 二、每个子任务的标准流程（强制）

```
Phase A: 设计
  帕托莉 → 编写 Task Brief (.md)
  帕托莉 → 发给 Claude Code: "先只做设计，不要写实现代码"
  Claude Code → 输出接口设计 / 类图 / 数据流
  帕托莉 → 检查设计完整性

Phase B: 评审（Design Review）
  帕托莉 → 汇报给 2ndElement: 设计方案 + 待决策点
  2ndElement → 确认 or 修改
  帕托莉 → 更新 DESIGN_DECISIONS.md

Phase C: 编码
  帕托莉 → 发给 Claude Code: "开始实现，严格按设计文档"
  Claude Code → 编写实现代码
  Claude Code → 编写对应单元测试

Phase D: 测试 & 评审（Code Review）
  Claude Code → 运行测试，报告结果
  帕托莉 → Code Review 要点检查
  帕托莉 → 汇报给 2ndElement: 完成情况 + 测试通过率

Phase E: 提交
  通过 → git commit (规范 message)
  未通过 → 返回 Phase C
```

---

## 三、CLAUDE.md 说明

每个服务目录下都有一个 `CLAUDE.md`，是 Claude Code 的工作说明书：

```
nexus-auth/CLAUDE.md          ← Java 认证服务专属说明
python-services/agent-engine/CLAUDE.md  ← Python Agent 专属说明
...
```

`CLAUDE.md` 包含：
1. 该服务的职责和边界
2. 技术约束（必须用什么，禁止用什么）
3. 当前任务描述（帕托莉每次任务前更新）
4. 测试要求（测试覆盖率要求、必须测哪些场景）
5. Code Review 检查清单

---

## 四、Code Review 检查清单（通用）

### Java 服务
- [ ] 所有数据库查询必须携带 `tenant_id` WHERE 条件
- [ ] ThreadLocal TenantContext 必须在 finally 块中 clear()
- [ ] Redis 缓存 key 必须包含 `tenantId`
- [ ] 统一用 `Result<T>` 包装返回值
- [ ] 异常必须统一处理，不允许裸 throw RuntimeException
- [ ] 所有 Controller 方法有 @Validated 参数校验
- [ ] 敏感字段（密码/Token）不入日志

### Python 服务
- [ ] 所有 LangGraph 调用必须传 `tenant_id` 在 config.configurable
- [ ] thread_id 格式必须是 `f"{tenant_id}:{conversation_id}"`
- [ ] FastAPI 路由必须依赖注入 `get_current_user`
- [ ] 异步函数必须有 timeout 设置
- [ ] Pydantic 模型覆盖所有入参/出参
- [ ] ChromaDB 查询必须带 `where={"tenant_id": tenant_id}` 过滤

### 通用
- [ ] 无硬编码密码/密钥
- [ ] 测试覆盖核心业务逻辑（≥80%）
- [ ] 有意义的变量名（无 a/b/tmp）
- [ ] 关键函数有注释说明

---

## 五、任务简报（Task Brief）模板

每次发给 Claude Code 之前，帕托莉必须填写：

```markdown
# Task Brief: [任务名称]

## 背景
[1-2 句话说明这个任务的上下文]

## 当前任务目标
[明确的交付物，例如：实现 /api/auth/login 接口]

## 技术约束
- 必须使用: [xxx]
- 禁止使用: [xxx]
- 依赖的其他服务: [xxx]

## 接口规范
[列出输入/输出格式]

## 测试要求
- [ ] 正常流程测试
- [ ] 边界条件测试
- [ ] 异常/错误测试

## 验收标准
- [ ] 测试全部通过
- [ ] Code Review 清单通过
- [ ] 无明显安全漏洞
```

---

## 六、编码顺序（Phase 1）

按依赖关系从底层到上层：

```
1. nexus-common          ← 公共模块（优先，其他模块依赖它）
2. nexus-auth            ← 认证服务（先有认证才能测其他）
3. nexus-gateway         ← 网关（认证通了再做路由）
4. nexus-tenant          ← 租户服务
5. agent-engine (Python) ← Agent 引擎（独立，可并行）
6. rag-service  (Python) ← RAG（依赖 ChromaDB）
7. nexus-session         ← 会话（依赖 auth + agent-engine）
```

---

## 七、Git 提交规范

```
feat(nexus-auth): 实现 JWT 登录接口
test(nexus-auth): 添加登录接口单元测试
fix(agent-engine): 修复多租户 thread_id 隔离问题
docs: 更新 ARCHITECTURE.md 容器环境说明
refactor(nexus-common): 统一 Result 响应封装
```

---

## 八、环境配置（容器内）

启动顺序：
```bash
# 1. MySQL (如未运行)
mysqld --user=mysql --bind-address=127.0.0.1 --port=3306 &

# 2. Redis
redis-server --daemonize yes --port 6379

# 3. Java 服务 (Maven)
cd nexus-auth && mvn spring-boot:run

# 4. Python 服务
cd python-services/agent-engine && uvicorn main:app --reload --port 8001
```

连接配置（开发环境固定）：
```
MySQL:  jdbc:mysql://127.0.0.1:3306/nexus_agent  user=nexus  pass=nexus_pass
Redis:  redis://127.0.0.1:6379
ChromaDB: 内存模式（测试）/ 文件模式（开发持久化）
```
