package tech.nexus.mcp.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import tech.nexus.mcp.service.AgentBindingService;

import java.util.Map;

@RestController
@RequestMapping("/api/agent/{agentId}/mcp")
@RequiredArgsConstructor
public class AgentBindingController {
    
    private final AgentBindingService bindingService;
    
    /**
     * 绑定 MCP Server 到 Agent
     */
    @PostMapping("/bind")
    public Map<String, Object> bind(
            @PathVariable Long agentId,
            @RequestBody Map<String, Long> request,
            @RequestHeader("X-Tenant-Id") Long tenantId) {
        Long mcpServerId = request.get("mcpServerId");
        return bindingService.bind(tenantId, agentId, mcpServerId);
    }
    
    /**
     * 解绑 MCP Server
     */
    @DeleteMapping("/{mcpServerId}")
    public Map<String, Object> unbind(
            @PathVariable Long agentId,
            @PathVariable Long mcpServerId,
            @RequestHeader("X-Tenant-Id") Long tenantId) {
        return bindingService.unbind(tenantId, agentId, mcpServerId);
    }
    
    /**
     * 获取 Agent 绑定的 MCP Servers
     */
    @GetMapping
    public Map<String, Object> list(
            @PathVariable Long agentId,
            @RequestHeader("X-Tenant-Id") Long tenantId) {
        return bindingService.listByAgent(tenantId, agentId);
    }
}
