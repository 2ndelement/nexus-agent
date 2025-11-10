package tech.nexus.common.context;

/**
 * 租户上下文（基于 ThreadLocal，线程安全隔离）。
 *
 * <p>使用方须在 finally 块中调用 {@link #clear()}，防止内存泄漏与线程池污染：
 * <pre>{@code
 * TenantContext.setTenantId(id);
 * try {
 *     // 业务逻辑
 * } finally {
 *     TenantContext.clear();
 * }
 * }</pre>
 */
public final class TenantContext {

    /** 普通 ThreadLocal，线程池场景由调用方负责传递 */
    private static final ThreadLocal<String> TENANT_ID_HOLDER = new ThreadLocal<>();

    private TenantContext() {
        // 工具类，不可实例化
    }

    /**
     * 设置当前线程的租户 ID。
     *
     * @param tenantId 租户 ID，不应为 null
     */
    public static void setTenantId(String tenantId) {
        TENANT_ID_HOLDER.set(tenantId);
    }

    /**
     * 获取当前线程的租户 ID。
     *
     * @return 租户 ID；若未设置则返回 {@code null}
     */
    public static String getTenantId() {
        return TENANT_ID_HOLDER.get();
    }

    /**
     * 清除当前线程的租户 ID。
     * <strong>必须在 finally 中调用！</strong>
     */
    public static void clear() {
        TENANT_ID_HOLDER.remove();
    }
}
