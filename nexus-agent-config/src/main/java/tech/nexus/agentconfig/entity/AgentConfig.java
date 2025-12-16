package tech.nexus.agentconfig.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * Agent 配置实体。
 */
@Data
@TableName("agent_config")
public class AgentConfig implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 租户 ID，多租户隔离 */
    private Long tenantId;

    /** Agent 名称 */
    private String name;

    /** 描述 */
    private String description;

    /** 头像 URL */
    private String avatar;

    /** 系统提示词（最大 64KB） */
    private String systemPrompt;

    /** 使用模型 */
    private String model;

    /** 温度参数：0.0 ~ 2.0 */
    private BigDecimal temperature;

    /** 最大 token 数 */
    private Integer maxTokens;

    /** 启用的工具列表（JSON 数组字符串） */
    private String tools;

    /** 绑定的知识库 ID 列表（JSON 数组字符串） */
    private String kbIds;

    /** 当前版本号 */
    private Integer version;

    /** 状态：1=发布 0=草稿 */
    private Integer status;

    /** 是否为平台公共模板：1=是 0=否 */
    private Integer isPublic;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;
}
