package tech.nexus.mcp.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tech.nexus.mcp.entity.AgentMCPServerBinding;
import tech.nexus.mcp.entity.MCPServer;
import tech.nexus.mcp.mapper.AgentMCPServerBindingMapper;
import tech.nexus.mcp.mapper.MCPServerMapper;

import java.time.LocalDateTime;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class AgentBindingService {
    
    private final AgentMCPServerBindingMapper bindingMapper;
    private final MCPServerMapper serverMapper;
    
    @Transactional
    public Map<String, Object> bind(Long tenantId, Long agentId, Long mcpServerId) {
        // 验证 MCP Server 存在且属于该租户
        MCPServer server = serverMapper.selectById(mcpServerId);
        if (server == null || !server.getTenantId().equals(tenantId)) {
            throw new RuntimeException("MCP Server 不存在");
        }
        
        // 检查是否已绑定
        LambdaQueryWrapper<AgentMCPServerBinding> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentMCPServerBinding::getAgentId, agentId)
                .eq(AgentMCPServerBinding::getMcpServerId, mcpServerId);
        if (bindingMapper.selectCount(wrapper) > 0) {
            throw new RuntimeException("该 MCP Server 已绑定到此 Agent");
        }
        
        // 创建绑定
        AgentMCPServerBinding binding = new AgentMCPServerBinding();
        binding.setAgentId(agentId);
        binding.setMcpServerId(mcpServerId);
        binding.setEnabled(true);
        binding.setCreatedAt(LocalDateTime.now());
        bindingMapper.insert(binding);
        
        log.info("绑定 MCP Server: agent={}, mcp={}", agentId, mcpServerId);
        
        return Map.of(
            "success", true,
            "message", "绑定成功"
        );
    }
    
    @Transactional
    public Map<String, Object> unbind(Long tenantId, Long agentId, Long mcpServerId) {
        LambdaQueryWrapper<AgentMCPServerBinding> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentMCPServerBinding::getAgentId, agentId)
                .eq(AgentMCPServerBinding::getMcpServerId, mcpServerId);
        
        int deleted = bindingMapper.delete(wrapper);
        if (deleted == 0) {
            throw new RuntimeException("绑定关系不存在");
        }
        
        log.info("解绑 MCP Server: agent={}, mcp={}", agentId, mcpServerId);
        
        return Map.of(
            "success", true,
            "message", "解绑成功"
        );
    }
    
    public Map<String, Object> listByAgent(Long tenantId, Long agentId) {
        LambdaQueryWrapper<AgentMCPServerBinding> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentMCPServerBinding::getAgentId, agentId)
                .eq(AgentMCPServerBinding::getEnabled, true);
        
        List<AgentMCPServerBinding> bindings = bindingMapper.selectList(wrapper);
        
        List<Map<String, Object>> servers = new ArrayList<>();
        for (AgentMCPServerBinding binding : bindings) {
            MCPServer server = serverMapper.selectById(binding.getMcpServerId());
            if (server != null && server.getStatus() == 1) {
                servers.add(Map.of(
                    "id", server.getId(),
                    "name", server.getName(),
                    "description", server.getDescription() != null ? server.getDescription() : ""
                ));
            }
        }
        
        return Map.of(
            "agentId", agentId,
            "servers", servers
        );
    }
}
