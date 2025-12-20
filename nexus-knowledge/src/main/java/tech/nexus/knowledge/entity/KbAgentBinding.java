package tech.nexus.knowledge.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 知识库与 Agent 绑定关系实体。
 */
@Data
@TableName("kb_agent_binding")
public class KbAgentBinding {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 租户ID */
    private Long tenantId;

    /** 知识库ID */
    private Long kbId;

    /** Agent ID */
    private Long agentId;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
}
