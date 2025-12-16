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
 * 工具注册表实体。
 */
@Data
@TableName("tool_registry")
public class ToolRegistry implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 工具唯一标识 */
    private String name;

    /** 显示名称 */
    private String displayName;

    /** 描述 */
    private String description;

    /** OpenAI function calling schema（JSON） */
    private String schema;

    /** 工具调用地址 */
    private String endpoint;

    /** 是否内置：1=内置 0=自定义 */
    private Integer isBuiltin;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
}
