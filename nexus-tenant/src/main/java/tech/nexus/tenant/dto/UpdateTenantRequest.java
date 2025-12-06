package tech.nexus.tenant.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 更新租户请求
 */
@Data
public class UpdateTenantRequest {

    /** 租户名称（可选更新） */
    private String name;

    /** 套餐（可选更新） */
    private String plan;

    /** 状态（可选更新） */
    private Integer status;
}
