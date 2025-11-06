# CLAUDE.md — nexus-gateway

> 本文件由帕托莉维护，Claude Code 必须在开始前完整阅读。

---

## 服务职责

`nexus-gateway` 是所有请求的统一入口，负责：
1. JWT Token 验证（从 nexus-auth 获取公钥/密钥）
2. Tenant ID 提取并注入到下游 Header
3. 路由转发（到各 Java/Python 微服务）
4. 限流（Sentinel，按租户）
5. 跨域（CORS）

---

## 技术约束

| 约束 | 说明 |
|------|------|
| **必须使用** | Spring Cloud Gateway 4.x, Spring Boot 3 |
| **必须使用** | nexus-common |
| **路由配置** | application.yml（不用代码路由） |
| **禁止** | Gateway 内不做业务逻辑 |
| **禁止** | 不做细粒度权限校验（只验证 Token 有效性） |
| **端口** | 8080 |

---

## 路由表

| 路径前缀 | 转发目标 | 备注 |
|---------|---------|------|
| /api/auth/** | http://localhost:8002 | 白名单，不需要 Token |
| /api/tenant/** | http://localhost:8003 | 需要 Token |
| /api/session/** | http://localhost:8004 | 需要 Token |
| /api/agent/** | http://localhost:8001 | 需要 Token，支持 SSE |
| /api/knowledge/** | http://localhost:8005 | 需要 Token |

---

## 核心 Filter 设计

```java
// AuthGlobalFilter (order = -100)
// 1. 白名单路径直接放行
// 2. 提取 Authorization: Bearer <token>
// 3. 验证 Token 有效性（本地验证，不调远程）
// 4. 从 Token 提取 tenantId, userId
// 5. 注入 Header: X-Tenant-Id, X-User-Id, X-Roles
// 6. 设置 TenantContext（可选，Gateway 本地用）
```

---

## 当前任务

### Task-03: 实现 nexus-gateway

**交付物：**

```
nexus-gateway/
├── pom.xml
└── src/main/
    ├── java/tech/nexus/gateway/
    │   ├── NexusGatewayApplication.java
    │   ├── filter/
    │   │   └── AuthGlobalFilter.java
    │   └── config/
    │       └── WhiteListConfig.java
    └── resources/
        └── application.yml      # 路由配置在这里
```

---

## 测试要求

- [ ] 携带有效 Token → 成功转发，下游收到 X-Tenant-Id Header
- [ ] 无 Token 访问受保护路径 → 401
- [ ] Token 过期 → 401
- [ ] 访问白名单路径（/api/auth/login）→ 直接放行
- [ ] SSE 路径不被 buffering（Content-Type: text/event-stream 透传）

---

## 注意事项

1. 开发阶段（容器内测试）：下游服务地址写 127.0.0.1，不用 Nacos
2. JWT 密钥与 nexus-auth 共享同一个 application.yml 配置
3. SSE 流式转发需确保 Gateway 不缓冲响应（`transfer-encoding: chunked`）
