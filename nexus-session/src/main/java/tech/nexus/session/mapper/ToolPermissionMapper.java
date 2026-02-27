package tech.nexus.session.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import tech.nexus.session.entity.ToolPermission;

import java.util.List;

/**
 * 工具权限 Mapper
 *
 * V5 重构：使用 owner_type + owner_id 替代 tenant_id + role_id
 */
@Mapper
public interface ToolPermissionMapper extends BaseMapper<ToolPermission> {

    /**
     * 查询用户允许的工具列表
     * V5: 根据 ownerType 和 ownerId 查询权限
     */
    @Select("SELECT tool_name FROM role_tool_permission " +
            "WHERE owner_type = #{ownerType} AND owner_id = #{ownerId} AND permission = 1")
    List<String> selectAllowedTools(@Param("ownerType") String ownerType, @Param("ownerId") Long ownerId, @Param("userId") Long userId);

    /**
     * 检查单个工具权限
     * V5: 使用 ownerType + ownerId
     */
    @Select("SELECT permission FROM role_tool_permission " +
            "WHERE owner_type = #{ownerType} AND owner_id = #{ownerId} " +
            "AND tool_name = #{toolName} AND tool_source = #{source}")
    Integer selectPermission(
        @Param("ownerType") String ownerType,
        @Param("ownerId") Long ownerId,
        @Param("userId") Long userId,
        @Param("toolName") String toolName,
        @Param("source") String source
    );
}
