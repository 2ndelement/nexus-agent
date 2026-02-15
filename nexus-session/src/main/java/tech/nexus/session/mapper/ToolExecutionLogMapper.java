package tech.nexus.session.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import tech.nexus.session.entity.ToolExecutionLog;

import java.util.List;

@Mapper
public interface ToolExecutionLogMapper extends BaseMapper<ToolExecutionLog> {
    
    @Select("SELECT * FROM tool_execution_log WHERE tenant_id = #{tenantId} AND conversation_id = #{conversationId} ORDER BY created_at DESC LIMIT 100")
    List<ToolExecutionLog> selectByConversation(@Param("tenantId") Long tenantId, @Param("conversationId") String conversationId);
}
