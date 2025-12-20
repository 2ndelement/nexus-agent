package tech.nexus.knowledge.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 知识库权限实体（多租户 RBAC 隔离）。
 *
 * <p>每条记录表示"某用户对某知识库拥有某角色权限"。
 * 角色：OWNER（拥有者）/ EDITOR（编辑）/ VIEWER（查看）
 */
@Data
@TableName("kb_permission")
public class KbPermission {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 租户ID */
    private Long tenantId;

    /** 知识库ID */
    private Long kbId;

    /** 用户ID */
    private Long userId;

    /**
     * 角色：OWNER / EDITOR / VIEWER
     */
    private String role;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
}
