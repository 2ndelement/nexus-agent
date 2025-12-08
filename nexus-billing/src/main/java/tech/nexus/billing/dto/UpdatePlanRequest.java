package tech.nexus.billing.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 修改租户套餐请求
 */
@Data
public class UpdatePlanRequest {

    @NotBlank(message = "planName 不能为空")
    private String planName;
}
