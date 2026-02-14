package tech.nexus.mcp.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import tech.nexus.mcp.entity.MCPServer;

import java.util.List;

@Mapper
public interface MCPServerMapper extends BaseMapper<MCPServer> {
    
    List<MCPServer> selectByTenantId(@Param("tenantId") Long tenantId);
    
    List<MCPServer> selectEnabledByTenantId(@Param("tenantId") Long tenantId);
    
    Long countByTenantId(@Param("tenantId") Long tenantId);
    
    void updateCallStats(@Param("id") Long id, @Param("success") boolean success);
}
