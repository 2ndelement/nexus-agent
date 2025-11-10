package tech.nexus.common.utils;

import tech.nexus.common.context.TenantContext;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.ResultCode;

/**
 * 租户工具类。
 */
public final class TenantUtils {

    private TenantUtils() {
        // 工具类，不可实例化
    }

    /**
     * 获取当前线程的租户 ID；若未设置则抛出业务异常。
     *
     * @return 租户 ID（非 null）
     * @throws BizException {@link ResultCode#TENANT_NOT_FOUND} 当租户 ID 未设置时
     */
    public static String requireTenantId() {
        String tenantId = TenantContext.getTenantId();
        if (tenantId == null || tenantId.isBlank()) {
            throw new BizException(ResultCode.TENANT_NOT_FOUND);
        }
        return tenantId;
    }
}
