package tech.nexus.knowledge.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import tech.nexus.knowledge.entity.DocumentChunk;

/**
 * 文档分片 Mapper。
 */
@Mapper
public interface DocumentChunkMapper extends BaseMapper<DocumentChunk> {
}
