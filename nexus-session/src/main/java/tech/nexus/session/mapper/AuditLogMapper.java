package tech.nexus.session.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import tech.nexus.session.entity.AuditLog;

import java.util.List;

@Mapper
public interface AuditLogMapper extends BaseMapper<AuditLog> {
    
    @Select("SELECT * FROM audit_log WHERE tenant_id = #{tenantId} ORDER BY created_at DESC LIMIT #{limit} OFFSET #{offset}")
    List<AuditLog> selectByTenant(@Param("tenantId") Long tenantId, @Param("limit") int limit, @Param("offset") int offset);
    
    @Select("SELECT * FROM audit_log WHERE tenant_id = #{tenantId} AND user_id = #{userId} ORDER BY created_at DESC LIMIT #{limit} OFFSET #{offset}")
    List<AuditLog> selectByUser(@Param("tenantId") Long tenantId, @Param("userId") Long userId, @Param("limit") int limit, @Param("offset") int offset);
}
