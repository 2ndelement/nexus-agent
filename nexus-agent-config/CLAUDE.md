# CLAUDE.md — nexus-agent-config

> 本文件由帕托莉维护，Claude Code 必须在开始前完整阅读。

---

## 服务职责

`nexus-agent-config` 是 Agent 配置管理服务，负责：
1. Agent 定义（名称、系统提示词、工具集、模型参数）的 CRUD
2. Agent 版本管理（支持回滚）
3. 工具（Tool）注册表管理
4. 租户级别的 Agent 模板发布与订阅
5. Agent 与知识库绑定关系（与 nexus-knowledge 协同）

**不负责：** Agent 实际执行（由 agent-engine 负责）、知识库文件管理（由 nexus-knowledge 负责）

---

## 技术约束

| 约束 | 说明 |
|------|------|
| **框架** | Spring Boot 3.x, MyBatis-Plus |
| **依赖** | nexus-common |
| **数据库** | MySQL 127.0.0.1:3306/nexus_agent |
| **缓存** | Redis（Agent 配置热缓存，减少 DB 查询） |
| **端口** | 8007 |

---

## 数据模型

```sql
CREATE TABLE `agent_config` (
  `id`            BIGINT AUTO_INCREMENT PRIMARY KEY,
  `tenant_id`     BIGINT NOT NULL,
  `name`          VARCHAR(100) NOT NULL COMMENT 'Agent 名称',
  `description`   TEXT COMMENT '描述',
  `avatar`        VARCHAR(500) COMMENT '头像 URL',
  `system_prompt` LONGTEXT COMMENT '系统提示词',
  `model`         VARCHAR(100) DEFAULT 'MiniMax-M2.5-highspeed' COMMENT '使用模型',
  `temperature`   DECIMAL(3,2) DEFAULT 0.70 COMMENT '温度参数',
  `max_tokens`    INT DEFAULT 2000,
  `tools`         JSON COMMENT '启用的工具列表 ["web_search","calculator"]',
  `kb_ids`        JSON COMMENT '绑定的知识库ID列表',
  `version`       INT DEFAULT 1 COMMENT '当前版本号',
  `status`        TINYINT DEFAULT 1 COMMENT '1=发布 0=草稿',
  `is_public`     TINYINT DEFAULT 0 COMMENT '1=平台模板 0=租户私有',
  `create_time`   DATETIME DEFAULT CURRENT_TIMESTAMP,
  `update_time`   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_tenant_name` (`tenant_id`, `name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `agent_config_history` (
  `id`            BIGINT AUTO_INCREMENT PRIMARY KEY,
  `agent_id`      BIGINT NOT NULL COMMENT '对应 agent_config.id',
  `tenant_id`     BIGINT NOT NULL,
  `version`       INT NOT NULL,
  `snapshot`      JSON NOT NULL COMMENT '完整配置快照',
  `change_note`   VARCHAR(500) COMMENT '变更说明',
  `create_time`   DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY `idx_agent_version` (`agent_id`, `version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `tool_registry` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `name`        VARCHAR(100) NOT NULL UNIQUE COMMENT '工具唯一标识',
  `display_name` VARCHAR(100) COMMENT '显示名称',
  `description` TEXT,
  `schema`      JSON COMMENT 'OpenAI function calling schema',
  `endpoint`    VARCHAR(500) COMMENT '工具调用地址（内部服务或外部URL）',
  `is_builtin`  TINYINT DEFAULT 1 COMMENT '1=内置 0=自定义',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 当前任务

### Task-09: 实现 nexus-agent-config 服务

**API 接口：**

```
POST   /api/agent-config/agents             创建 Agent
GET    /api/agent-config/agents             列出（分页，支持按名称搜索）
GET    /api/agent-config/agents/{id}        获取详情
PUT    /api/agent-config/agents/{id}        更新（自动保存历史版本）
DELETE /api/agent-config/agents/{id}        删除

GET    /api/agent-config/agents/{id}/history          版本历史列表
POST   /api/agent-config/agents/{id}/rollback/{ver}   回滚到指定版本

GET    /api/agent-config/tools              工具注册表列表（内置工具）

GET    /api/agent-config/templates          平台公共模板列表（is_public=1）
POST   /api/agent-config/templates/{id}/fork  从模板 fork 一个私有副本
```

**Redis 缓存：**
```
key: nexus:{tenantId}:agent:{agentId}:config  → Agent 完整配置，TTL 5min
更新/删除时主动失效缓存
```

---

## 测试要求

- [ ] 创建 Agent → 版本号为 1
- [ ] 更新 Agent → 版本号 +1，历史表有记录
- [ ] 回滚到 v1 → 当前配置恢复为 v1 内容，版本号继续 +1（不覆盖历史）
- [ ] 租户A的 Agent 不能被租户B查询
- [ ] is_public=1 的模板所有租户可查询

---

## Code Review 检查清单

- [ ] 更新时必须先写入 history 表再更新主表（顺序不能反）
- [ ] temperature 范围校验：0.0 ~ 2.0
- [ ] system_prompt 长度限制：64KB
- [ ] tools 字段必须校验工具是否在 tool_registry 中注册
- [ ] Redis 缓存 key 必须含 tenantId

---

## 内置工具（预置数据）

| 工具名 | 说明 |
|-------|------|
| `web_search` | 网页搜索 |
| `calculator` | 数学计算 |
| `knowledge_retrieval` | 检索绑定的知识库 |
| `code_interpreter` | 代码执行（规划中） |

---

## 注意事项

1. 先输出 Agent 更新+版本管理的设计（核心逻辑），等帕托莉确认再写代码
2. 测试用 H2 内存库
