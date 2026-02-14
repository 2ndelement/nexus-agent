package tech.nexus.mcp.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

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
    private String detail;
    private String ipAddress;
    private String userAgent;
    private Integer result;
    private String errorMessage;
    
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
