package tech.nexus.session.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 会话实体。
 *
 * V5 重构：使用 owner_type + owner_id 替代 tenant_id
 * - owner_type: PERSONAL 或 ORGANIZATION
 * - owner_id: 用户ID(PERSONAL) 或 组织ID(ORGANIZATION)
 */
@Data
@TableName("conversation")
public class Conversation implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 自增主键 */
    @TableId(type = IdType.AUTO)
    private Long id;

    /** 会话ID (UUID) */
    private String conversationId;

    /** 所有者类型：PERSONAL 或 ORGANIZATION */
    private String ownerType;

    /** 所有者ID：用户ID(PERSONAL) 或 组织ID(ORGANIZATION) */
    private Long ownerId;

    /** 兼容旧版 schema 的租户ID，V5 下与 ownerId 保持一致 */
    private Long tenantId;

    /** 用户ID */
    private Long userId;

    /** 会话标题 */
    private String title;

    /** 使用的 Agent配置ID */
    private Long agentId;

    /** 使用的模型 */
    private String model;

    /**
     * 会话状态：1=活跃，0=已归档
     */
    private Integer status;

    /** 消息数量 */
    private Integer messageCount;

    /** 会话开始时的可用工具列表（JSON） */
    private String toolList;

    /** 创建时间 */
    @TableField(fill = com.baomidou.mybatisplus.annotation.FieldFill.INSERT)
    private LocalDateTime createTime;

    /** 更新时间 */
    @TableField(fill = com.baomidou.mybatisplus.annotation.FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;
}
