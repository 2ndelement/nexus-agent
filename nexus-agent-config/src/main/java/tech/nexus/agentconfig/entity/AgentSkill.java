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
 * Agent 与 Skill 绑定关系实体。
 */
@Data
@TableName("agent_skill")
public class AgentSkill implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.AUTO)
    private Long id;

    /** Agent 配置 ID */
    private Long agentId;

    /** Skill 名称 */
    private String skillName;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
}
