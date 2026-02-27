package tech.nexus.session.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * Bot 实体。
 *
 * 代表一个机器人配置，可以绑定到 Agent。
 * 同一 Agent 可绑定多个不同平台的 Bot（QQ、飞书等）。
 */
@Data
@TableName("bot")
public class Bot implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 自增主键 */
    @TableId(type = IdType.AUTO)
    private Long id;

    /** Bot 名称 */
    private String botName;

    /**
     * 平台类型：QQ, QQ_GUILD, FEISHU, WECHAT, TELEGRAM, WEB
     */
    private String platform;

    /** 平台 AppID */
    private String appId;

    /** 平台 AppSecret（加密存储） */
    private String appSecret;

    /** Bot Token */
    private String botToken;

    /** 绑定的 Agent 配置 ID */
    private Long agentId;

    /**
     * 归属类型：PERSONAL（个人空间）或 ORGANIZATION（组织空间）
     */
    private String ownerType;

    /** 归属 ID（用户 ID 或组织 ID） */
    private Long ownerId;

    /** 状态：1=启用，0=禁用 */
    private Integer status;

    /** 平台特定配置（JSON） */
    private String config;

    /** 创建时间 */
    @TableField(fill = FieldFill.INSERT, value = "created_at")
    private LocalDateTime createTime;

    /** 更新时间 */
    @TableField(fill = FieldFill.INSERT_UPDATE, value = "updated_at")
    private LocalDateTime updateTime;
}
