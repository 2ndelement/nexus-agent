package tech.nexus.session.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * BotBinding 实体。
 *
 * 代表用户与 Bot 的绑定关系。
 * 通过 puid（平台用户 ID）将外部平台用户映射到 Nexus 内部用户。
 */
@Data
@TableName("bot_binding")
public class BotBinding implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 自增主键 */
    @TableId(type = IdType.AUTO)
    private Long id;

    /** Bot ID */
    private Long botId;

    /** Nexus 用户 ID */
    private Long userId;

    /** 平台用户 ID（puid） */
    private String puid;

    /** 平台特定数据（JSON），如昵称、头像等 */
    private String extraData;

    /** 状态：1=正常，0=已解绑 */
    private Integer status;

    /** 创建时间 */
    @TableField(fill = FieldFill.INSERT, value = "created_at")
    private LocalDateTime createTime;

    /** 更新时间 */
    @TableField(fill = FieldFill.INSERT_UPDATE, value = "updated_at")
    private LocalDateTime updateTime;
}
