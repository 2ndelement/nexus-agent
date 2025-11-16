# CLAUDE.md — nexus-platform

> 本文件由帕托莉维护，Claude Code 必须在开始前完整阅读。

---

## 服务职责

`nexus-platform` 是平台管理服务（超级管理员后台），负责：
1. 平台级用户管理（超管账户，独立于租户体系）
2. 租户的开通、审批、禁用（平台维度）
3. 全局系统配置（LLM 接入配置、功能开关）
4. 平台级监控数据汇总（各租户用量概览）
5. 公告/通知管理

**访问权限：** 只有 `ROLE_PLATFORM_ADMIN` 才能访问此服务，普通租户用户无权限。

---

## 技术约束

| 约束 | 说明 |
|------|------|
| **框架** | Spring Boot 3.x, MyBatis-Plus |
| **依赖** | nexus-common |
| **数据库** | MySQL 127.0.0.1:3306/nexus_agent |
| **安全** | 所有接口额外校验 ROLE_PLATFORM_ADMIN（双重保障，Gateway + 服务层） |
| **端口** | 8009 |

---

## 数据模型

```sql
-- 全局系统配置
CREATE TABLE `system_config` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `config_key`  VARCHAR(100) NOT NULL UNIQUE COMMENT '配置键',
  `config_value` TEXT COMMENT '配置值（JSON/字符串）',
  `description` VARCHAR(500),
  `is_public`   TINYINT DEFAULT 0 COMMENT '1=对租户可见',
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 公告
CREATE TABLE `announcement` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `title`       VARCHAR(200) NOT NULL,
  `content`     TEXT NOT NULL,
  `level`       VARCHAR(20) DEFAULT 'INFO' COMMENT 'INFO/WARNING/URGENT',
  `target`      VARCHAR(20) DEFAULT 'ALL' COMMENT 'ALL/PLAN:PRO/TENANT:xxx',
  `status`      TINYINT DEFAULT 1 COMMENT '1=发布 0=草稿',
  `publish_time` DATETIME,
  `expire_time` DATETIME,
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 当前任务

### Task-11: 实现 nexus-platform 基础功能

**API 接口（全部需要 ROLE_PLATFORM_ADMIN）：**

```
# 租户管理
GET    /api/platform/tenants                    所有租户列表（分页、可按名称/套餐筛选）
GET    /api/platform/tenants/{id}               租户详情（含用量概览）
PUT    /api/platform/tenants/{id}/status        启用/禁用租户
POST   /api/platform/tenants                    手动开通租户

# 系统配置
GET    /api/platform/config                     所有配置列表
PUT    /api/platform/config/{key}               更新配置
GET    /api/platform/config/public              公开配置（无需管理员权限，租户可查）

# 公告
POST   /api/platform/announcements              创建公告
GET    /api/platform/announcements              公告列表
PUT    /api/platform/announcements/{id}         更新
DELETE /api/platform/announcements/{id}         删除

# 数据概览（Dashboard）
GET    /api/platform/dashboard                  全局统计（租户数、DAU、总Token消耗等）
```

**常用系统配置键（预置）：**

| config_key | 说明 | 默认值 |
|-----------|------|--------|
| `llm.default_model` | 默认 LLM 模型 | `MiniMax-M2.5-highspeed` |
| `llm.api_base_url` | LLM API 基础地址 | `https://copilot.lab.2ndelement.tech/v1` |
| `feature.registration_enabled` | 是否开放注册 | `true` |
| `feature.free_plan_enabled` | 是否提供免费套餐 | `true` |
| `upload.max_file_size_mb` | 文档上传大小上限 | `50` |

---

## 测试要求

- [ ] 普通租户 Token 访问平台接口 → 403 Forbidden
- [ ] 平台管理员可以禁用租户
- [ ] 系统配置更新后立即生效（Redis 缓存失效）
- [ ] Dashboard 接口返回格式正确

---

## Code Review 检查清单

- [ ] 所有接口在 Controller 层再次校验 PLATFORM_ADMIN 角色（不只依赖 Gateway）
- [ ] 禁用租户时发送系统通知（可以只记日志，Phase 2 再接消息队列）
- [ ] 系统配置变更有操作审计日志
- [ ] Dashboard 数据可以允许有 1-5 分钟缓存（高频查询）

---

## 注意事项

1. 平台管理员账户在初始化时预置（数据库初始化脚本），不通过注册创建
2. 此服务在 Phase 1 中**优先级较低**，可在其他模块完成后实现
3. 先设计接口，等帕托莉确认再编码
