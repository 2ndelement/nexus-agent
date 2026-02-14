package tech.nexus.mcp.dto;

import lombok.Data;
import java.time.LocalDateTime;
import java.util.Map;

@Data
public class MCPServerResponse {
    private Long id;
    private Long tenantId;
    private String name;
    private String description;
    private String configType;
    private Map<String, Object> config;
    private Integer status;
    private Long totalCalls;
    private Long failedCalls;
    private Double successRate;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
