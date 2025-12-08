package tech.nexus.billing.dto;

import lombok.Builder;
import lombok.Data;

/**
 * 配额检查响应
 */
@Data
@Builder
public class CheckQuotaResponse {

    /** 是否允许本次调用 */
    private boolean allowed;

    /** 今日剩余 API 调用次数 */
    private long remainingCalls;

    /** 今日剩余 Token 数 */
    private long remainingTokens;

    /** 拒绝原因（allowed=false 时有值） */
    private String reason;
}
