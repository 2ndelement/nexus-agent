package tech.nexus.billing.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

/**
 * 用量上报请求
 */
@Data
public class UsageReportRequest {

    @NotNull(message = "tenantId 不能为空")
    private Long tenantId;

    @NotBlank(message = "model 不能为空")
    private String model;

    @Min(value = 0, message = "inputTokens 不能为负数")
    private Long inputTokens = 0L;

    @Min(value = 0, message = "outputTokens 不能为负数")
    private Long outputTokens = 0L;
}
