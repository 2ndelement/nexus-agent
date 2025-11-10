package tech.nexus.common.constant;

/**
 * Nexus 全局常量。
 */
public final class NexusConstants {

    private NexusConstants() {
        // 常量类，不可实例化
    }

    // ── HTTP Header ──────────────────────────────────────────

    /** 租户 ID 请求头 */
    public static final String HEADER_TENANT_ID = "X-Tenant-Id";

    /** 认证令牌请求头 */
    public static final String HEADER_AUTHORIZATION = "Authorization";

    /** Bearer Token 前缀 */
    public static final String BEARER_PREFIX = "Bearer ";

    // ── Redis Key 前缀 ────────────────────────────────────────

    /** 用户 Token 缓存前缀：token:{tenantId}:{userId} */
    public static final String REDIS_KEY_TOKEN_PREFIX = "token:";

    /** 租户信息缓存前缀：tenant:{tenantId} */
    public static final String REDIS_KEY_TENANT_PREFIX = "tenant:";

    /** 用户信息缓存前缀：user:{tenantId}:{userId} */
    public static final String REDIS_KEY_USER_PREFIX = "user:";

    // ── 分页默认值 ────────────────────────────────────────────

    public static final int DEFAULT_PAGE_NUMBER = 1;
    public static final int DEFAULT_PAGE_SIZE = 20;
    public static final int MAX_PAGE_SIZE = 500;
}
