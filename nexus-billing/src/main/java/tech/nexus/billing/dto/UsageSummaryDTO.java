package tech.nexus.billing.dto;

import lombok.Data;

import java.time.LocalDate;

/**
 * 用量汇总 DTO（按天聚合）
 */
@Data
public class UsageSummaryDTO {

    private LocalDate statDate;
    private Long totalApiCalls;
    private Long totalInputTokens;
    private Long totalOutputTokens;
}
