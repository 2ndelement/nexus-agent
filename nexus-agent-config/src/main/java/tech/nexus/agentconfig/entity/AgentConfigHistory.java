package tech.nexus.agentconfig.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * Agent 配置历史版本实体。
 */
@Data
@TableName("agent_config_history")
public class AgentConfigHistory implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 对应 agent_config.id */
    private Long agentId;

    /** 租户 ID */
    private Long tenantId;

    /** 版本号 */
    private Integer version;

    /** 完整配置快照（JSON） */
    private String snapshot;

    /** 变更说明 */
    private String changeNote;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
}
