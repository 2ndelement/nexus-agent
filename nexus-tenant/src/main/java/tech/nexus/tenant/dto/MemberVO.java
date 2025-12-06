package tech.nexus.tenant.dto;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 成员信息响应 DTO
 */
@Data
public class MemberVO {
    private Long id;
    private Long tenantId;
    private Long userId;
    private String role;
    private Integer status;
    private LocalDateTime createTime;
}
