package tech.nexus.billing.dto;

import lombok.Builder;
import lombok.Data;

import java.util.List;

/**
 * 用量查询响应（按日期范围汇总）
 */
@Data
@Builder
public class UsageQueryResponse {

    private Long tenantId;
    private String startDate;
    private String endDate;
    private long totalApiCalls;
    private long totalInputTokens;
    private long totalOutputTokens;
    private List<UsageSummaryDTO> dailyDetails;
}
