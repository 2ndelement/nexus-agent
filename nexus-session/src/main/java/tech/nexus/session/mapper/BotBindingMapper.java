package tech.nexus.session.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import tech.nexus.session.entity.BotBinding;

import java.util.List;
import java.util.Optional;

@Mapper
public interface BotBindingMapper extends BaseMapper<BotBinding> {

    /**
     * 根据 Bot ID 和 puid 查询绑定
     */
    @Select("SELECT * FROM bot_binding WHERE bot_id = #{botId} AND puid = #{puid} AND status = 1 LIMIT 1")
    Optional<BotBinding> findByBotIdAndPuid(@Param("botId") Long botId, @Param("puid") String puid);

    /**
     * 根据用户 ID 查询所有绑定
     */
    @Select("SELECT * FROM bot_binding WHERE user_id = #{userId} AND status = 1")
    List<BotBinding> findByUserId(@Param("userId") Long userId);

    /**
     * 根据 Bot ID 查询所有绑定
     */
    @Select("SELECT * FROM bot_binding WHERE bot_id = #{botId} AND status = 1")
    List<BotBinding> findByBotId(@Param("botId") Long botId);

    /**
     * 根据用户 ID 和 Bot ID 查询绑定
     */
    @Select("SELECT * FROM bot_binding WHERE user_id = #{userId} AND bot_id = #{botId} AND status = 1 LIMIT 1")
    Optional<BotBinding> findByUserIdAndBotId(@Param("userId") Long userId, @Param("botId") Long botId);
}
