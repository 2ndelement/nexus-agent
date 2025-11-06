# CLAUDE.md — nexus-common

> 本文件由帕托莉维护，Claude Code 必须在开始前完整阅读。

---

## 服务职责

`nexus-common` 是整个 Java 后端的公共依赖包，**不是独立服务**，打包为 JAR 供其他模块引用。

核心内容：
1. 统一 API 响应结构 `Result<T>`
2. 全局异常处理
3. 租户上下文 `TenantContext`（ThreadLocal）
4. 通用工具类（JWT 工具、分页工具等）
5. 通用实体基类（`BaseEntity`）
6. 统一错误码枚举

---

## 技术约束

| 约束 | 说明 |
|------|------|
| **必须使用** | Spring Boot 3.x, Java 21, Maven |
| **必须使用** | Lombok (简化 getter/setter) |
| **必须使用** | jjwt 0.12.x (JWT 工具) |
| **禁止** | 不能引入 Web 层依赖（无 Controller） |
| **禁止** | 不能有数据库连接依赖 |
| **禁止** | 不允许使用 hutool（避免不必要的大依赖） |

---

## 当前任务

### Task-01: 实现 nexus-common 基础框架

**交付物：**

```
nexus-common/
├── pom.xml
└── src/main/java/tech/nexus/common/
    ├── result/
    │   ├── Result.java              # 统一响应
    │   ├── ResultCode.java          # 错误码枚举
    │   └── PageResult.java          # 分页响应
    ├── context/
    │   └── TenantContext.java       # 租户上下文（ThreadLocal）
    ├── entity/
    │   └── BaseEntity.java          # 基础实体（id, tenantId, createTime, updateTime）
    ├── exception/
    │   ├── BizException.java        # 业务异常
    │   └── GlobalExceptionHandler.java  # 全局处理（由 web 模块引入生效）
    ├── utils/
    │   ├── JwtUtils.java            # JWT 工具（签发/解析/验证）
    │   └── TenantUtils.java         # 租户工具
    └── constant/
        └── NexusConstants.java      # 常量（Header名、Redis前缀等）
```

**接口规范：**

```java
// Result<T>
Result.success(data)           // 200 + data
Result.success()               // 200 + null
Result.fail(ResultCode.xxx)    // 错误码
Result.fail(code, msg)         // 自定义消息

// ResultCode 枚举
SUCCESS(200, "操作成功")
UNAUTHORIZED(401, "未认证")
FORBIDDEN(403, "无权限")
NOT_FOUND(404, "资源不存在")
PARAM_ERROR(400, "参数错误")
TENANT_NOT_FOUND(1001, "租户不存在")
TENANT_DISABLED(1002, "租户已禁用")
USER_NOT_FOUND(2001, "用户不存在")
USER_DISABLED(2002, "用户已禁用")
TOKEN_EXPIRED(3001, "Token 已过期")
TOKEN_INVALID(3002, "Token 无效")

// TenantContext
TenantContext.setTenantId(String tenantId)
TenantContext.getTenantId() -> String
TenantContext.clear()                      // 必须在 finally 中调用！

// JwtUtils
JwtUtils.generateToken(userId, tenantId, roles) -> String
JwtUtils.parseToken(token) -> Claims
JwtUtils.isExpired(token) -> boolean
```

---

## 测试要求

```
nexus-common/src/test/java/tech/nexus/common/
├── result/
│   └── ResultTest.java          # Result 构建、序列化
├── context/
│   └── TenantContextTest.java   # ThreadLocal 隔离、clear 不泄露
├── utils/
│   └── JwtUtilsTest.java        # 签发、解析、过期、篡改检测
└── exception/
    └── BizExceptionTest.java    # 异常构建
```

**必须覆盖的测试场景：**
- [ ] Result.success() 序列化为 `{"code":200,"msg":"操作成功","data":null}`
- [ ] Result.fail() 包含正确 code 和 msg
- [ ] TenantContext 多线程场景下不互相污染（模拟两个线程各自设置不同 tenantId）
- [ ] TenantContext.clear() 后 getTenantId() 返回 null
- [ ] JwtUtils 生成的 Token 可以正确解析出 userId 和 tenantId
- [ ] JwtUtils 检测篡改的 Token 抛出异常
- [ ] JwtUtils 检测过期 Token（设置极短过期时间测试）

---

## Code Review 检查清单

- [ ] TenantContext 使用 `InheritableThreadLocal` 还是 `ThreadLocal`？
  > 答：普通 ThreadLocal 即可，线程池场景由调用方负责传递
- [ ] JwtUtils 密钥是否硬编码？
  > 必须从配置读取，不能写死
- [ ] BaseEntity 中 tenantId 是否有 @Column(nullable=false) 注解？
- [ ] ResultCode 枚举是否有重复 code 值？
- [ ] 所有工具类是否 final + 私有构造（不可实例化）？

---

## 注意事项

1. **先输出设计（类图/接口列表），等帕托莉确认后再写代码**
2. 测试必须用 JUnit 5，不用 JUnit 4
3. pom.xml 中 `<scope>test</scope>` 正确标注测试依赖
4. 生成代码后**立即运行 `mvn test`** 并报告结果
5. 如果 Maven 下载依赖超时，告知帕托莉处理
