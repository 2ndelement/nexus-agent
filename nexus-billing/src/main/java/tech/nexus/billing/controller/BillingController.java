package tech.nexus.billing.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import tech.nexus.billing.dto.*;
import tech.nexus.billing.service.BillingService;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.Result;
import tech.nexus.common.result.ResultCode;

import java.time.LocalDate;

/**
 * 计费控制器
 *
 * <p>接口设计遵循 CLAUDE.md 规范：
 * <ul>
 *   <li>POST /api/billing/check-quota        配额检查（消耗型）</li>
 *   <li>POST /api/billing/usage/report       用量上报</li>
 *   <li>GET  /api/billing/usage              用量查询</li>
 *   <li>GET  /api/billing/quota              当前配额余量</li>
 *   <li>PUT  /api/billing/tenants/{id}/plan  修改套餐（管理员）</li>
 * </ul>
 */
@RestController
@RequestMapping("/api/billing")
@RequiredArgsConstructor
public class BillingController {

    private final BillingService billingService;

    /**
     * 配额检查（消耗型）。
     * 超限时返回 HTTP 429。
     */
    @PostMapping("/check-quota")
    public Result<CheckQuotaResponse> checkQuota(@Valid @RequestBody CheckQuotaRequest request) {
        CheckQuotaResponse response = billingService.checkQuota(request);
        if (!response.isAllowed()) {
            // 超限直接抛出异常，由全局处理器转换为 429
            throw new QuotaExceededException(response);
        }
        return Result.success(response);
    }

    /**
     * 用量上报。
     */
    @PostMapping("/usage/report")
    public Result<Void> reportUsage(@Valid @RequestBody UsageReportRequest request) {
        billingService.reportUsage(request);
        return Result.success();
    }

    /**
     * 用量查询（按日期范围）。
     * 若未传 tenantId，要求调用方传递（内部服务调用场景）。
     */
    @GetMapping("/usage")
    public Result<UsageQueryResponse> queryUsage(
            @RequestParam Long tenantId,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate startDate,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate endDate) {

        if (startDate.isAfter(endDate)) {
            throw new BizException(ResultCode.PARAM_ERROR, "startDate 不能晚于 endDate");
        }
        return Result.success(billingService.queryUsage(tenantId, startDate, endDate));
    }

    /**
     * 查询当前租户配额余量。
     */
    @GetMapping("/quota")
    public Result<QuotaInfoResponse> getQuotaInfo(@RequestParam Long tenantId) {
        return Result.success(billingService.getQuotaInfo(tenantId));
    }

    /**
     * 修改租户套餐（平台管理员接口）。
     */
    @PutMapping("/tenants/{id}/plan")
    public Result<Void> updateTenantPlan(
            @PathVariable("id") Long tenantId,
            @Valid @RequestBody UpdatePlanRequest request) {
        billingService.updateTenantPlan(tenantId, request);
        return Result.success();
    }

    // ─── 内部异常类：配额超限 → HTTP 429 ────────────────────────────────────

    /**
     * 配额超限专用异常，全局处理器拦截后返回 429。
     */
    @ResponseStatus(HttpStatus.TOO_MANY_REQUESTS)
    public static class QuotaExceededException extends RuntimeException {

        private final CheckQuotaResponse detail;

        public QuotaExceededException(CheckQuotaResponse detail) {
            super(detail.getReason());
            this.detail = detail;
        }

        public CheckQuotaResponse getDetail() {
            return detail;
        }
    }
}
