package tech.nexus.mcp.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("agent_mcp_binding")
public class AgentMCPServerBinding {
    
    @TableId(type = IdType.AUTO)
    private Long id;
    
    private Long agentId;
    private Long mcpServerId;
    private Boolean enabled;
    
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
