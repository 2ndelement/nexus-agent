package tech.nexus.tenant.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 租户用户关联实体（成员表）
 */
@Data
@TableName("tenant_user")
public class TenantUser {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 租户 ID（多租户隔离核心字段） */
    private Long tenantId;

    /** 用户 ID */
    private Long userId;

    /** 角色：OWNER / ADMIN / MEMBER */
    private String role;

    /** 状态：1=启用 0=禁用 */
    private Integer status;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
}
