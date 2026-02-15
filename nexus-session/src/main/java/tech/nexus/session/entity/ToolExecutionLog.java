package tech.nexus.session.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 工具调用记录
 */
@Data
@TableName("tool_execution_log")
public class ToolExecutionLog {
    
    @TableId(type = IdType.AUTO)
    private Long id;
    
    private Long auditLogId;
    private Long tenantId;
    private Long userId;
    private Long agentId;
    private String conversationId;
    
    /** 工具名称 */
    private String toolName;
    
    /** 工具来源：BUILTIN / MCP / CUSTOM */
    private String toolSource;
    
    /** 调用参数 */
    private String arguments;
    
    /** 执行结果 */
    private String result;
    
    /** 状态：1=成功 0=失败 */
    private Integer status;
    
    /** 错误信息 */
    private String errorMessage;
    
    /** 执行耗时（毫秒） */
    private Integer durationMs;
    
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
