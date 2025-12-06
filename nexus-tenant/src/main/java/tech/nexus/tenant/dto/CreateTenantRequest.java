package tech.nexus.tenant.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 创建租户请求
 */
@Data
public class CreateTenantRequest {

    @NotBlank(message = "租户名称不能为空")
    private String name;

    /** 套餐，默认 FREE */
    private String plan = "FREE";
}
