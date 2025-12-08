package tech.nexus.billing.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

/**
 * 配额检查请求
 */
@Data
public class CheckQuotaRequest {

    @NotNull(message = "tenantId 不能为空")
    private Long tenantId;

    /** 预估消耗 Token 数（0 表示只检查 API 调用次数限制） */
    @Min(value = 0, message = "estimatedTokens 不能为负数")
    private Long estimatedTokens = 0L;
}
