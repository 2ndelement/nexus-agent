package tech.nexus.session.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 审计日志
 */
@Data
@TableName("audit_log")
public class AuditLog {
    
    @TableId(type = IdType.AUTO)
    private Long id;
    
    private Long tenantId;
    private Long userId;
    private String actionType;
    private String resourceType;
    private String resourceId;
    
    /** 操作详情 JSON */
    private String detail;
    
    private String ipAddress;
    private String userAgent;
    
    /** 1=成功 0=失败 */
    private Integer result;
    private String errorMessage;
    
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
