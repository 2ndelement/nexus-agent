package tech.nexus.session.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import tech.nexus.session.entity.Conversation;

/**
 * 会话 Mapper。
 *
 * <p>继承 MyBatis-Plus BaseMapper，所有查询通过 Service 层附加 tenant_id 条件。
 */
@Mapper
public interface ConversationMapper extends BaseMapper<Conversation> {
}
