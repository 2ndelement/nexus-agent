package tech.nexus.billing.dto;

import lombok.Builder;
import lombok.Data;

import java.time.LocalDate;

/**
 * 配额余量查询响应
 */
@Data
@Builder
public class QuotaInfoResponse {

    private Long tenantId;
    private String planName;
    private String planDisplayName;

    /** 每日 API 调用上限（含额外购买） */
    private long maxApiCallsDay;

    /** 每日 Token 上限（含额外购买） */
    private long maxTokensDay;

    /** 今日已用 API 调用次数 */
    private long usedApiCalls;

    /** 今日已用 Token 数 */
    private long usedTokens;

    /** 今日剩余 API 调用次数 */
    private long remainingCalls;

    /** 今日剩余 Token 数 */
    private long remainingTokens;

    /** 套餐到期日，null = 永久 */
    private LocalDate validUntil;
}
