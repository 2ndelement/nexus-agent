package tech.nexus.session.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 工具权限实体
 *
 * V5 重构：使用 owner_type + owner_id 替代 tenant_id + role_id
 */
@Data
@TableName("role_tool_permission")
public class ToolPermission {
    @TableId(type = IdType.AUTO)
    private Long id;

    /** 所有者类型：PERSONAL 或 ORGANIZATION */
    private String ownerType;

    /** 所有者ID：用户ID(PERSONAL) 或 组织ID(ORGANIZATION) */
    private Long ownerId;

    /** 用户ID */
    private Long userId;

    private String toolName;
    private String toolSource;
    private Integer permission;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
