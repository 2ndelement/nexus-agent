package tech.nexus.knowledge.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import tech.nexus.knowledge.entity.KbAgentBinding;

/**
 * 知识库-Agent 绑定 Mapper。
 */
@Mapper
public interface KbAgentBindingMapper extends BaseMapper<KbAgentBinding> {
}
