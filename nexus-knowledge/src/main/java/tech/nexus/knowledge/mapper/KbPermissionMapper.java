package tech.nexus.knowledge.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import tech.nexus.knowledge.entity.KbPermission;

/**
 * 知识库权限 Mapper。
 */
@Mapper
public interface KbPermissionMapper extends BaseMapper<KbPermission> {
}
