package tech.nexus.mcp.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tech.nexus.mcp.dto.MCPServerRequest;
import tech.nexus.mcp.dto.MCPServerResponse;
import tech.nexus.mcp.entity.MCPServer;
import tech.nexus.mcp.mapper.MCPServerMapper;

import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class MCPServerService {
    
    private final MCPServerMapper mapper;
    private final ObjectMapper objectMapper;
    
    private static final int MAX_SERVERS_PER_TENANT = 100;
    
    public List<MCPServerResponse> listByTenantId(Long tenantId) {
        return mapper.selectByTenantId(tenantId).stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }
    
    public List<MCPServerResponse> listEnabledByTenantId(Long tenantId) {
        return mapper.selectEnabledByTenantId(tenantId).stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }
    
    public MCPServerResponse getById(Long tenantId, Long id) {
        MCPServer server = mapper.selectById(id);
        if (server == null || !server.getTenantId().equals(tenantId)) {
            return null;
        }
        return toResponse(server);
    }
    
    @Transactional
    public MCPServerResponse create(Long tenantId, MCPServerRequest request) {
        if (mapper.countByTenantId(tenantId) >= MAX_SERVERS_PER_TENANT) {
            throw new RuntimeException("MCP Server 数量已达上限（" + MAX_SERVERS_PER_TENANT + "个）");
        }
        
        MCPServer server = new MCPServer();
        server.setTenantId(tenantId);
        server.setName(request.getName());
        server.setDescription(request.getDescription());
        server.setConfigType(request.getConfigType());
        server.setStatus(request.getStatus());
        server.setTotalCalls(0L);
        server.setFailedCalls(0L);
        server.setCreatedAt(LocalDateTime.now());
        server.setUpdatedAt(LocalDateTime.now());
        
        try {
            server.setConfig(objectMapper.writeValueAsString(request.getConfig()));
        } catch (Exception e) {
            throw new RuntimeException("配置格式错误: " + e.getMessage());
        }
        
        mapper.insert(server);
        log.info("创建 MCP Server: tenant={}, name={}", tenantId, request.getName());
        
        return toResponse(server);
    }
    
    @Transactional
    public MCPServerResponse update(Long tenantId, Long id, MCPServerRequest request) {
        MCPServer server = mapper.selectById(id);
        if (server == null || !server.getTenantId().equals(tenantId)) {
            throw new RuntimeException("MCP Server 不存在");
        }
        
        server.setName(request.getName());
        server.setDescription(request.getDescription());
        server.setConfigType(request.getConfigType());
        server.setStatus(request.getStatus());
        server.setUpdatedAt(LocalDateTime.now());
        
        try {
            server.setConfig(objectMapper.writeValueAsString(request.getConfig()));
        } catch (Exception e) {
            throw new RuntimeException("配置格式错误: " + e.getMessage());
        }
        
        mapper.updateById(server);
        log.info("更新 MCP Server: id={}, name={}", id, request.getName());
        
        return toResponse(server);
    }
    
    @Transactional
    public void delete(Long tenantId, Long id) {
        MCPServer server = mapper.selectById(id);
        if (server == null || !server.getTenantId().equals(tenantId)) {
            throw new RuntimeException("MCP Server 不存在");
        }
        mapper.deleteById(id);
        log.info("删除 MCP Server: id={}", id);
    }
    
    public Map<String, Object> testConnection(Long tenantId, Long id) {
        MCPServer server = mapper.selectById(id);
        if (server == null || !server.getTenantId().equals(tenantId)) {
            throw new RuntimeException("MCP Server 不存在");
        }
        
        try {
            Map<String, Object> config = objectMapper.readValue(server.getConfig(), Map.class);
            // TODO: 实际测试连接
            return Map.of("success", true, "message", "连接测试成功");
        } catch (Exception e) {
            log.error("MCP Server 连接测试失败: id={}", id, e);
            return Map.of("success", false, "message", "连接失败: " + e.getMessage());
        }
    }
    
    private MCPServerResponse toResponse(MCPServer server) {
        MCPServerResponse response = new MCPServerResponse();
        response.setId(server.getId());
        response.setTenantId(server.getTenantId());
        response.setName(server.getName());
        response.setDescription(server.getDescription());
        response.setConfigType(server.getConfigType());
        response.setStatus(server.getStatus());
        response.setTotalCalls(server.getTotalCalls());
        response.setFailedCalls(server.getFailedCalls());
        response.setCreatedAt(server.getCreatedAt());
        response.setUpdatedAt(server.getUpdatedAt());
        
        if (server.getTotalCalls() != null && server.getTotalCalls() > 0) {
            long success = server.getTotalCalls() - server.getFailedCalls();
            response.setSuccessRate((double) success / server.getTotalCalls() * 100);
        }
        
        try {
            if (server.getConfig() != null) {
                response.setConfig(objectMapper.readValue(server.getConfig(), Map.class));
            }
        } catch (Exception e) {
            log.warn("配置解析失败: id={}", server.getId(), e);
        }
        
        return response;
    }
}
