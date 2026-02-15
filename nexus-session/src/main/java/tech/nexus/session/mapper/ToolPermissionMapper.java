package tech.nexus.session.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import tech.nexus.session.entity.ToolPermission;

import java.util.List;

/**
 * 工具权限 Mapper
 */
@Mapper
public interface ToolPermissionMapper extends BaseMapper<ToolPermission> {
    
    /**
     * 查询角色允许的工具列表
     */
    @Select("SELECT tool_name FROM role_tool_permission " +
            "WHERE tenant_id = #{tenantId} AND role_id = #{roleId} AND permission = 1")
    List<String> selectAllowedTools(@Param("tenantId") Long tenantId, @Param("roleId") Long roleId);
    
    /**
     * 检查单个工具权限
     */
    @Select("SELECT permission FROM role_tool_permission " +
            "WHERE tenant_id = #{tenantId} AND role_id = #{roleId} " +
            "AND tool_name = #{toolName} AND tool_source = #{source}")
    Integer selectPermission(
        @Param("tenantId") Long tenantId,
        @Param("roleId") Long roleId,
        @Param("toolName") String toolName,
        @Param("source") String source
    );
}
