# CLAUDE.md — nexus-tenant

> 本文件由帕托莉维护，Claude Code 必须在开始前完整阅读。

---

## 服务职责

`nexus-tenant` 管理租户的全生命周期：
1. 租户 CRUD
2. 租户用户成员管理（邀请/踢除/角色设置）
3. 租户配置与套餐管理

---

## 技术约束

| 约束 | 说明 |
|------|------|
| 框架 | Spring Boot 3, MyBatis-Plus |
| 数据库 | MySQL 127.0.0.1:3306/nexus_agent |
| 端口 | 8003 |
| 禁止 | 不能操作其他租户的数据（强制 tenant_id 隔离） |

---

## 数据模型

```sql
CREATE TABLE `tenant` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `name`        VARCHAR(100) NOT NULL,
  `plan`        VARCHAR(20) DEFAULT 'FREE',
  `status`      TINYINT DEFAULT 1,
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE `tenant_user` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `tenant_id`   BIGINT NOT NULL,
  `user_id`     BIGINT NOT NULL,
  `role`        VARCHAR(20) DEFAULT 'MEMBER',  -- OWNER/ADMIN/MEMBER
  `status`      TINYINT DEFAULT 1,
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_tenant_user` (`tenant_id`, `user_id`)
);
```

---

## 当前任务

### Task-04: 实现 nexus-tenant 基础 CRUD

**API 接口：**
```
POST   /api/tenant/          创建租户（系统管理员用）
GET    /api/tenant/{id}      查询租户信息
PUT    /api/tenant/{id}      更新租户配置
POST   /api/tenant/{id}/members       添加成员
DELETE /api/tenant/{id}/members/{uid} 移除成员
GET    /api/tenant/{id}/members       成员列表
```

---

## 测试要求

- [ ] 创建租户 → 返回租户 ID
- [ ] 添加成员 → 成员列表能查到
- [ ] 成员只能看到自己所在租户的数据
- [ ] 重复添加同一成员 → 幂等处理

---

## 注意事项

1. 先设计接口和 DB 表，等帕托莉确认再编码
2. 测试用 H2 内存库
