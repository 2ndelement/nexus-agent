package tech.nexus.mcp.dto;

import lombok.Data;
import jakarta.validation.constraints.*;
import java.util.Map;

@Data
public class MCPServerRequest {
    
    @NotBlank(message = "名称不能为空")
    @Size(max = 100, message = "名称最多100字符")
    private String name;
    
    @Size(max = 500, message = "描述最多500字符")
    private String description;
    
    @NotBlank(message = "传输类型不能为空")
    @Pattern(regexp = "sse|streamable_http", message = "传输类型必须是 sse 或 streamable_http")
    private String configType;
    
    @NotNull(message = "配置不能为空")
    private Map<String, Object> config;
    
    private Integer status = 1;
}
