# CLAUDE.md — nexus-billing

> 本文件由帕托莉维护，Claude Code 必须在开始前完整阅读。

---

## 服务职责

`nexus-billing` 是计费与配额管理服务，负责：
1. 租户套餐（Plan）与配额（Quota）管理
2. API 调用次数、Token 消耗的实时统计
3. 配额超限检查（被其他服务调用前置校验）
4. 用量账单查询（按天/月汇总）
5. 配额告警（接近上限时通知）

**不负责：** 实际支付（规划中，当前只做用量统计）、认证

---

## 技术约束

| 约束 | 说明 |
|------|------|
| **框架** | Spring Boot 3.x, MyBatis-Plus |
| **依赖** | nexus-common |
| **数据库** | MySQL 127.0.0.1:3306/nexus_agent |
| **计数器** | Redis（实时配额消耗，高频写，用 INCR 原子操作） |
| **端口** | 8008 |

---

## 数据模型

```sql
-- 套餐定义
CREATE TABLE `plan` (
  `id`               BIGINT AUTO_INCREMENT PRIMARY KEY,
  `name`             VARCHAR(50) NOT NULL UNIQUE COMMENT 'FREE/PRO/ENTERPRISE',
  `display_name`     VARCHAR(100),
  `max_users`        INT DEFAULT 5,
  `max_agents`       INT DEFAULT 3,
  `max_api_calls_day` INT DEFAULT 1000 COMMENT '每日 API 调用次数上限',
  `max_tokens_day`   BIGINT DEFAULT 100000 COMMENT '每日 Token 上限',
  `max_kb_size_mb`   INT DEFAULT 100 COMMENT '知识库容量上限(MB)',
  `price_monthly`    DECIMAL(10,2) DEFAULT 0.00,
  `create_time`      DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 租户配额
CREATE TABLE `tenant_quota` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `tenant_id`   BIGINT NOT NULL UNIQUE,
  `plan_id`     BIGINT NOT NULL,
  `extra_calls` INT DEFAULT 0 COMMENT '额外购买的调用次数',
  `extra_tokens` BIGINT DEFAULT 0,
  `valid_until` DATE COMMENT '套餐到期日，NULL=永久',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 用量记录（按天汇总，不存明细）
CREATE TABLE `usage_daily` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `tenant_id`   BIGINT NOT NULL,
  `stat_date`   DATE NOT NULL COMMENT '统计日期',
  `api_calls`   INT DEFAULT 0,
  `input_tokens` BIGINT DEFAULT 0,
  `output_tokens` BIGINT DEFAULT 0,
  `model`       VARCHAR(100) COMMENT '模型名称',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_tenant_date_model` (`tenant_id`, `stat_date`, `model`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 当前任务

### Task-10: 实现 nexus-billing 服务

**API 接口：**

```
# 配额检查（被其他服务内部调用）
POST  /api/billing/check-quota          检查配额是否充足
      Body: { "tenantId": 1, "estimatedTokens": 500 }
      Resp: { "allowed": true, "remainingCalls": 800 }

# 用量上报（被 agent-engine 调用完成后上报）
POST  /api/billing/usage/report
      Body: { "tenantId": 1, "model": "MiniMax-M2.5-highspeed",
              "inputTokens": 100, "outputTokens": 300 }

# 用量查询
GET   /api/billing/usage?startDate=2026-03-01&endDate=2026-03-17  当月用量
GET   /api/billing/quota    查询当前租户配额余量

# 管理接口（平台管理员用）
PUT   /api/billing/tenants/{id}/plan    修改租户套餐
```

**Redis 实时计数器：**
```
key: nexus:{tenantId}:quota:calls:{date}   INCR + EXPIRE（到当日23:59:59）
key: nexus:{tenantId}:quota:tokens:{date}  INCRBY tokens + EXPIRE

配额检查逻辑：
1. Redis INCR 当日计数
2. 若超限 → 回滚 DECR，返回 allowed=false
3. 日终定时任务将 Redis 数据 flush 到 usage_daily 表
```

---

## 测试要求

- [ ] 配额检查：未超限返回 allowed=true，超限返回 allowed=false
- [ ] 用量上报：Redis INCR 原子操作，不丢计数
- [ ] 不同租户配额计数完全独立
- [ ] 用量汇总查询正确按日期范围聚合

---

## Code Review 检查清单

- [ ] Redis INCR 必须设 EXPIRE，防止 key 永久存在
- [ ] 配额检查是幂等的还是消耗型的？（应该是消耗型，先扣后回滚）
- [ ] usage_daily 的 UPSERT 用 ON DUPLICATE KEY UPDATE
- [ ] 超限响应码必须是 429（Too Many Requests）

---

## 预置套餐数据（SQL）

```sql
INSERT INTO plan (name, display_name, max_users, max_agents, max_api_calls_day, max_tokens_day, max_kb_size_mb) VALUES
('FREE',       '免费版',   5,    3,   1000,    100000,  100),
('PRO',        '专业版',  50,   20,  10000,   2000000, 1024),
('ENTERPRISE', '企业版', 500, 1000, 100000, 100000000, 10240);
```

---

## 注意事项

1. 日终 flush 任务先不实现（Phase 2 再做），当前 usage_daily 由 report 接口直接写
2. 测试时 Redis 配额计数可以用真实 Redis（127.0.0.1:6379）
3. 先设计配额检查的核心流程，等帕托莉确认再编码
