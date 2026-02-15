package tech.nexus.session.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import tech.nexus.session.mapper.ToolPermissionMapper;

import java.util.*;

/**
 * 工具服务
 * 
 * 获取用户可用的工具列表
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ToolService {
    
    private final ToolPermissionMapper toolPermissionMapper;
    
    // 内置工具定义
    private static final List<Map<String, Object>> BUILTIN_TOOLS = Arrays.asList(
        Map.of(
            "name", "calculator",
            "source", "BUILTIN",
            "description", "计算器 - 执行数学表达式计算"
        ),
        Map.of(
            "name", "web_search",
            "source", "BUILTIN",
            "description", "网络搜索 - 搜索互联网获取实时信息"
        ),
        Map.of(
            "name", "sandbox_execute",
            "source", "BUILTIN",
            "description", "代码执行 - 在隔离沙箱中执行Python或Bash代码，支持timeout参数（1-3600秒）"
        )
    );
    
    /**
     * 获取用户可用的工具列表
     * 
     * @param tenantId 租户ID
     * @param roleId 角色ID
     * @return 工具列表
     */
    public Map<String, Object> getAvailableTools(Long tenantId, Long roleId) {
        List<Map<String, Object>> tools = new ArrayList<>();
        
        // 1. 添加内置工具
        tools.addAll(BUILTIN_TOOLS);
        
        // 2. 查询角色权限允许的工具
        List<String> allowedTools = toolPermissionMapper.selectAllowedTools(tenantId, roleId);
        
        // 3. 过滤工具列表（只保留允许的）
        // 内置工具默认全部允许
        // 自定义工具需要检查权限
        
        return Map.of(
            "updated_at", new Date(),
            "tools", tools
        );
    }
    
    /**
     * 检查用户是否有工具权限
     */
    public boolean checkPermission(Long tenantId, Long roleId, String toolName, String source) {
        // 内置工具默认允许
        if ("BUILTIN".equals(source)) {
            return true;
        }
        
        // 检查权限表
        Integer permission = toolPermissionMapper.selectPermission(tenantId, roleId, toolName, source);
        return permission != null && permission == 1;
    }
}
