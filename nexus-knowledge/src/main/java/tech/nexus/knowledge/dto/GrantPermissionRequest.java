package tech.nexus.knowledge.dto;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import lombok.Data;

/**
 * 授予知识库权限请求 DTO。
 */
@Data
public class GrantPermissionRequest {

    @NotNull(message = "用户ID不能为空")
    private Long userId;

    /**
     * 角色：OWNER / EDITOR / VIEWER
     */
    @NotNull(message = "角色不能为空")
    @Pattern(regexp = "OWNER|EDITOR|VIEWER", message = "角色必须是 OWNER、EDITOR 或 VIEWER")
    private String role;
}
