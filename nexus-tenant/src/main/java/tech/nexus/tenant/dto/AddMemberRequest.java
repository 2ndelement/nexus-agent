package tech.nexus.tenant.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

/**
 * 添加成员请求
 */
@Data
public class AddMemberRequest {

    @NotNull(message = "用户ID不能为空")
    private Long userId;

    /** 角色，默认 MEMBER */
    private String role = "MEMBER";
}
