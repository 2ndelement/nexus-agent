# CLAUDE.md — nexus-auth

> 本文件由帕托莉维护，Claude Code 必须在开始前完整阅读。

---

## 服务职责

`nexus-auth` 是独立的认证微服务，负责：
1. 用户注册 / 登录
2. JWT Access Token + Refresh Token 签发
3. Token 刷新与注销
4. 用户密码管理

**不负责：** RBAC 权限校验（由各微服务自行校验）、租户管理（由 nexus-tenant 负责）

---

## 技术约束

| 约束 | 说明 |
|------|------|
| **必须使用** | Spring Boot 3.x, Java 21, Maven |
| **必须使用** | MyBatis-Plus 3.5.x（ORM） |
| **必须使用** | nexus-common（公共依赖） |
| **必须使用** | BCrypt 加密密码（Spring Security Crypto） |
| **数据库** | MySQL 127.0.0.1:3306/nexus_agent, user=nexus, pass=nexus_pass |
| **缓存** | Redis 127.0.0.1:6379（存 Refresh Token / 黑名单） |
| **禁止** | 明文存储密码 |
| **禁止** | Token 信息存到 MySQL（用 Redis） |
| **端口** | 8002 |

---

## 当前任务

### Task-02: 实现 nexus-auth 认证服务

**交付物：**

```
nexus-auth/
├── pom.xml
├── src/main/
│   ├── java/tech/nexus/auth/
│   │   ├── NexusAuthApplication.java
│   │   ├── controller/
│   │   │   └── AuthController.java
│   │   ├── service/
│   │   │   ├── AuthService.java (interface)
│   │   │   └── impl/AuthServiceImpl.java
│   │   ├── mapper/
│   │   │   └── UserMapper.java
│   │   ├── entity/
│   │   │   └── User.java
│   │   └── dto/
│   │       ├── LoginRequest.java
│   │       ├── RegisterRequest.java
│   │       └── TokenResponse.java
│   └── resources/
│       ├── application.yml
│       └── mapper/UserMapper.xml
└── src/test/java/tech/nexus/auth/
    ├── controller/AuthControllerTest.java
    └── service/AuthServiceTest.java
```

**数据库表：**

```sql
CREATE TABLE `user` (
  `id`          BIGINT NOT NULL AUTO_INCREMENT,
  `tenant_id`   BIGINT NOT NULL COMMENT '租户ID',
  `username`    VARCHAR(50) NOT NULL COMMENT '用户名',
  `email`       VARCHAR(100) COMMENT '邮箱',
  `password`    VARCHAR(100) NOT NULL COMMENT 'BCrypt密码',
  `roles`       VARCHAR(200) DEFAULT 'USER' COMMENT '角色，逗号分隔',
  `status`      TINYINT DEFAULT 1 COMMENT '1=正常 0=禁用',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_tenant_username` (`tenant_id`, `username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**API 接口：**

```
POST /api/auth/register
Body: { "tenantId": 1, "username": "alice", "password": "xxx", "email": "a@b.com" }
Resp: Result<TokenResponse>

POST /api/auth/login
Body: { "tenantId": 1, "username": "alice", "password": "xxx" }
Resp: Result<TokenResponse>

POST /api/auth/refresh
Body: { "refreshToken": "xxx" }
Resp: Result<TokenResponse>

POST /api/auth/logout
Header: Authorization: Bearer <token>
Resp: Result<Void>

GET  /api/auth/me
Header: Authorization: Bearer <token>
Resp: Result<UserInfo>
```

**TokenResponse 格式：**
```json
{
  "accessToken": "eyJ...",
  "refreshToken": "eyJ...",
  "expiresIn": 7200,
  "tokenType": "Bearer"
}
```

---

## 测试要求

**必须覆盖的场景：**
- [ ] 正常注册 → 返回 Token
- [ ] 重复注册同 tenantId+username → 400 错误
- [ ] 正常登录 → Token 可解析出正确 userId 和 tenantId
- [ ] 错误密码登录 → 401 错误
- [ ] 用 Access Token 访问 /me → 返回用户信息
- [ ] 用过期 Token 访问 → 401 错误
- [ ] Refresh Token 刷新 → 新 Access Token
- [ ] Logout 后 Token 进入黑名单 → 再次访问 401

**测试使用 Spring Boot Test + H2 内存库（不依赖外部 MySQL）**

---

## Code Review 检查清单

- [ ] 密码必须 BCrypt 加密存储
- [ ] Redis 中 Refresh Token key: `nexus:{tenantId}:refresh:{userId}`
- [ ] Redis 黑名单 key: `nexus:blacklist:{accessToken的jti}`
- [ ] 登录失败不能暴露"用户不存在"还是"密码错误"（统一返回"用户名或密码错误"）
- [ ] 所有接口参数有 @NotBlank / @NotNull 校验
- [ ] 测试中无真实密钥硬编码（用测试专用配置）

---

## 注意事项

1. 先输出接口设计和 DB 表结构，等帕托莉确认后再写代码
2. 使用 H2 数据库做单元测试（不依赖外部 MySQL）
3. 测试完成后运行 `mvn test`，报告测试通过情况
