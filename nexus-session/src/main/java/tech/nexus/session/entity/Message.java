package tech.nexus.session.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 消息实体。
 *
 * <p>对应数据库 {@code message} 表，消息 ID 使用数据库自增。
 *
 * V5 重构：使用 owner_type + owner_id 替代 tenant_id
 */
@Data
@TableName("message")
public class Message implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 消息ID，数据库自增 */
    @TableId(type = IdType.AUTO)
    private Long id;

    /** 所属会话ID */
    private String conversationId;

    /** 所有者类型：PERSONAL 或 ORGANIZATION */
    private String ownerType;

    /** 所有者ID：用户ID(PERSONAL) 或 组织ID(ORGANIZATION) */
    private Long ownerId;

    /** 兼容旧版 schema 的租户ID，V5 下与 ownerId 保持一致 */
    private Long tenantId;

    /** 消息角色：user/assistant/system/tool */
    private String role;

    /** 消息内容 */
    private String content;

    /** token 消耗数 */
    private Integer tokens;

    /** 工具调用结果、引用来源等附加元数据（JSON 字符串） */
    private String metadata;

    /** 幂等Key，用于防止重复写入 */
    @TableField("idempotent_key")
    private String idempotentKey;

    /** 创建时间 */
    @TableField(fill = com.baomidou.mybatisplus.annotation.FieldFill.INSERT)
    private LocalDateTime createTime;
}
