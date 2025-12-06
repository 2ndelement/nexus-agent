package tech.nexus.tenant.dto;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 租户信息响应 DTO
 */
@Data
public class TenantVO {
    private Long id;
    private String name;
    private String plan;
    private Integer status;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
