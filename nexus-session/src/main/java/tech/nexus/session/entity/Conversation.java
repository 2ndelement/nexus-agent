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
 * <p>对应数据库 {@code conversation} 表，convId 使用 UUID 字符串，非自增。
 */
@Data
@TableName("conversation")
public class Conversation implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 会话ID (UUID) */
    @TableId(type = IdType.INPUT)
    private String id;

    /** 租户ID，多租户隔离核心字段 */
    private Long tenantId;

    /** 用户ID */
    private Long userId;

    /** 对话标题 */
    private String title;

    /** 使用的 Agent 配置ID */
    private Long agentId;

    /** 使用的模型 */
    private String model;

    /**
     * 会话状态：1=活跃，0=已归档
     */
    private Integer status;

    /** 消息数量 */
    private Integer messageCount;

    /** 创建时间 */
    @TableField(fill = com.baomidou.mybatisplus.annotation.FieldFill.INSERT)
    private LocalDateTime createTime;

    /** 更新时间 */
    @TableField(fill = com.baomidou.mybatisplus.annotation.FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;
}
