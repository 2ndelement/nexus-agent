# CLAUDE.md — nexus-session

> 本文件由帕托莉维护，Claude Code 必须在开始前完整阅读。

---

## 服务职责

`nexus-session` 是会话管理服务，负责：
1. 会话（Conversation）的 CRUD 管理
2. 历史消息持久化到 MySQL
3. 会话元数据（标题、摘要、模型配置等）维护
4. 为 agent-engine 提供会话上下文查询

**不负责：** 实际 AI 对话执行（由 agent-engine 负责）、认证（由 Gateway 负责）

---

## 技术约束

| 约束 | 说明 |
|------|------|
| **框架** | Spring Boot 3.x, MyBatis-Plus 3.5.x |
| **依赖** | nexus-common |
| **数据库** | MySQL 127.0.0.1:3306/nexus_agent, user=nexus, pass=nexus_pass |
| **缓存** | Redis 127.0.0.1:6379（会话状态热数据） |
| **禁止** | 会话数据不能跨租户查询 |
| **端口** | 8004 |

---

## 数据模型

```sql
CREATE TABLE `conversation` (
  `id`            VARCHAR(64) NOT NULL COMMENT '会话ID (UUID)',
  `tenant_id`     BIGINT NOT NULL COMMENT '租户ID',
  `user_id`       BIGINT NOT NULL COMMENT '用户ID',
  `title`         VARCHAR(200) DEFAULT '新对话' COMMENT '对话标题',
  `agent_id`      BIGINT COMMENT '使用的 Agent 配置ID',
  `model`         VARCHAR(100) DEFAULT 'MiniMax-M2.5-highspeed' COMMENT '使用的模型',
  `status`        TINYINT DEFAULT 1 COMMENT '1=活跃 0=已归档',
  `message_count` INT DEFAULT 0,
  `create_time`   DATETIME DEFAULT CURRENT_TIMESTAMP,
  `update_time`   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_tenant_user` (`tenant_id`, `user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `message` (
  `id`              BIGINT AUTO_INCREMENT PRIMARY KEY,
  `conversation_id` VARCHAR(64) NOT NULL,
  `tenant_id`       BIGINT NOT NULL COMMENT '冗余字段，便于隔离查询',
  `role`            VARCHAR(20) NOT NULL COMMENT 'user/assistant/system/tool',
  `content`         LONGTEXT NOT NULL,
  `tokens`          INT DEFAULT 0 COMMENT 'token 消耗数',
  `metadata`        JSON COMMENT '工具调用结果、引用来源等',
  `create_time`     DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY `idx_conv_time` (`conversation_id`, `create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 当前任务

### Task-07: 实现 nexus-session 基础服务

**交付物：**

```
nexus-session/
├── pom.xml
└── src/main/java/tech/nexus/session/
    ├── NexusSessionApplication.java
    ├── controller/
    │   ├── ConversationController.java
    │   └── MessageController.java
    ├── service/impl/
    │   ├── ConversationServiceImpl.java
    │   └── MessageServiceImpl.java
    ├── mapper/
    │   ├── ConversationMapper.java
    │   └── MessageMapper.java
    └── entity/
        ├── Conversation.java
        └── Message.java
```

**API 接口：**

```
POST   /api/session/conversations                   创建会话
GET    /api/session/conversations                   列出当前用户所有会话（分页）
GET    /api/session/conversations/{id}              获取会话详情
DELETE /api/session/conversations/{id}              删除（归档）会话
PUT    /api/session/conversations/{id}/title        更新标题

GET    /api/session/conversations/{id}/messages     获取消息历史（分页，按时间升序）
POST   /api/session/conversations/{id}/messages     追加消息（由 agent-engine 调用）
DELETE /api/session/conversations/{id}/messages     清空消息
```

**Redis 缓存策略：**
```
key: nexus:{tenantId}:conv:{convId}:meta  → 会话元数据，TTL 30min
key: nexus:{tenantId}:conv:{convId}:msgs:recent  → 最近20条消息，TTL 10min
```

---

## 测试要求

- [ ] 创建会话 → 返回 UUID convId
- [ ] 同一租户不同用户只能看自己的会话
- [ ] 不同租户的 convId 相同也能共存（无冲突）
- [ ] 消息按 create_time 升序返回
- [ ] 删除会话后消息也不可查询

**测试用 H2 内存库 + Mockito（不依赖外部 Redis 时用 Mock）**

---

## Code Review 检查清单

- [ ] 所有查询必须 WHERE tenant_id = #{tenantId}
- [ ] convId 生成用 UUID.randomUUID()，不用自增 ID
- [ ] 消息追加接口做幂等设计（防重复写入）
- [ ] Redis key 必须包含 tenantId

---

## 注意事项

先设计接口 + 数据表，等帕托莉确认后再编码。测试完成后 mvn test 全绿再 commit。
