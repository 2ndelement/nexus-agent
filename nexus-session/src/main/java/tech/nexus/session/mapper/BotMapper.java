package tech.nexus.session.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import tech.nexus.session.entity.Bot;

import java.util.List;

@Mapper
public interface BotMapper extends BaseMapper<Bot> {

    /**
     * 根据平台和 AppID 查询 Bot
     */
    @Select("SELECT * FROM bot WHERE platform = #{platform} AND app_id = #{appId} AND status = 1 LIMIT 1")
    Bot findByPlatformAndAppId(@Param("platform") String platform, @Param("appId") String appId);

    /**
     * 根据 Agent ID 查询所有 Bot
     */
    @Select("SELECT * FROM bot WHERE agent_id = #{agentId} AND status = 1")
    List<Bot> findByAgentId(@Param("agentId") Long agentId);

    /**
     * 根据 owner 查询所有 Bot
     */
    @Select("SELECT * FROM bot WHERE owner_type = #{ownerType} AND owner_id = #{ownerId} AND status = 1")
    List<Bot> findByOwner(@Param("ownerType") String ownerType, @Param("ownerId") Long ownerId);
}
