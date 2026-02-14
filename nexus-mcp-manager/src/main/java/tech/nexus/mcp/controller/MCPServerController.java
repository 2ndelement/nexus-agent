package tech.nexus.mcp.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import tech.nexus.mcp.dto.MCPServerRequest;
import tech.nexus.mcp.dto.MCPServerResponse;
import tech.nexus.mcp.service.MCPServerService;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/mcp/servers")
@RequiredArgsConstructor
public class MCPServerController {
    
    private final MCPServerService service;
    
    @GetMapping
    public List<MCPServerResponse> list(@RequestHeader("X-Tenant-Id") Long tenantId) {
        return service.listByTenantId(tenantId);
    }
    
    @GetMapping("/{id}")
    public MCPServerResponse get(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @PathVariable Long id) {
        MCPServerResponse server = service.getById(tenantId, id);
        if (server == null) {
            throw new RuntimeException("MCP Server 不存在");
        }
        return server;
    }
    
    @PostMapping
    public MCPServerResponse create(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @Valid @RequestBody MCPServerRequest request) {
        return service.create(tenantId, request);
    }
    
    @PutMapping("/{id}")
    public MCPServerResponse update(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @PathVariable Long id,
            @Valid @RequestBody MCPServerRequest request) {
        return service.update(tenantId, id, request);
    }
    
    @DeleteMapping("/{id}")
    public void delete(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @PathVariable Long id) {
        service.delete(tenantId, id);
    }
    
    @PostMapping("/{id}/test")
    public Map<String, Object> testConnection(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @PathVariable Long id) {
        return service.testConnection(tenantId, id);
    }
}
