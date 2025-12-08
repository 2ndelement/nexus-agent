package tech.nexus.billing.service;

import tech.nexus.billing.dto.*;

import java.time.LocalDate;

/**
 * 计费服务接口
 */
public interface BillingService {

    /**
     * 检查租户配额是否充足（消耗型：先扣后回滚）。
     * 超限时 HTTP 响应码应为 429。
     *
     * @param request 包含 tenantId 和 estimatedTokens
     * @return 检查结果，allowed=true 表示允许，false 表示超限
     */
    CheckQuotaResponse checkQuota(CheckQuotaRequest request);

    /**
     * 上报一次 API 调用的用量（由 agent-engine 在调用完成后异步/同步上报）。
     *
     * @param request 包含 tenantId、model、inputTokens、outputTokens
     */
    void reportUsage(UsageReportRequest request);

    /**
     * 查询租户在指定日期范围内的用量汇总。
     *
     * @param tenantId  租户 ID
     * @param startDate 开始日期
     * @param endDate   结束日期
     * @return 用量查询响应
     */
    UsageQueryResponse queryUsage(Long tenantId, LocalDate startDate, LocalDate endDate);

    /**
     * 查询租户当前配额余量。
     *
     * @param tenantId 租户 ID
     * @return 配额余量信息
     */
    QuotaInfoResponse getQuotaInfo(Long tenantId);

    /**
     * 修改租户套餐（管理员接口）。
     *
     * @param tenantId 租户 ID
     * @param request  包含新套餐名称
     */
    void updateTenantPlan(Long tenantId, UpdatePlanRequest request);
}
