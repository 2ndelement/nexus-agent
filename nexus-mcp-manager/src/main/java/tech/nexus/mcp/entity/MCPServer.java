package tech.nexus.mcp.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * MCP Server 配置实体
 */
@Data
@TableName("mcp_server")
public class MCPServer {
    
    @TableId(type = IdType.AUTO)
    private Long id;
    
    private Long tenantId;
    private String name;
    private String description;
    private String configType;
    private String config;
    private Integer status;
    private Long totalCalls;
    private Long failedCalls;
    
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
    
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
