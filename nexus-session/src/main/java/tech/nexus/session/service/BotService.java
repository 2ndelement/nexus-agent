package tech.nexus.session.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import tech.nexus.common.result.PageResult;
import tech.nexus.session.entity.Bot;
import tech.nexus.session.mapper.BotMapper;

import java.util.List;
import java.util.Optional;

/**
 * Bot 服务
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class BotService {

    private final BotMapper botMapper;

    /**
     * 根据平台和 AppID 查找 Bot
     */
    public Optional<Bot> findByPlatformAndAppId(String platform, String appId) {
        return Optional.ofNullable(botMapper.findByPlatformAndAppId(platform, appId));
    }

    /**
     * 根据 ID 查找 Bot
     */
    public Optional<Bot> findById(Long id) {
        return Optional.ofNullable(botMapper.selectById(id));
    }

    /**
     * 根据 Agent ID 查找所有 Bot
     */
    public List<Bot> findByAgentId(Long agentId) {
        return botMapper.findByAgentId(agentId);
    }

    /**
     * 根据 Owner 查找所有 Bot
     */
    public List<Bot> findByOwner(String ownerType, Long ownerId) {
        return botMapper.findByOwner(ownerType, ownerId);
    }

    /**
     * 创建 Bot
     */
    public Bot createBot(Bot bot) {
        botMapper.insert(bot);
        log.info("[BotService] 创建 Bot: id={}, name={}, platform={}",
                bot.getId(), bot.getBotName(), bot.getPlatform());
        return bot;
    }

    /**
     * 更新 Bot
     */
    public Bot updateBot(Bot bot) {
        botMapper.updateById(bot);
        log.info("[BotService] 更新 Bot: id={}", bot.getId());
        return bot;
    }

    /**
     * 删除 Bot（软删除）
     */
    public void deleteBot(Long id) {
        Bot bot = new Bot();
        bot.setId(id);
        bot.setStatus(0);
        botMapper.updateById(bot);
        log.info("[BotService] 删除 Bot: id={}", id);
    }

    /**
     * 分页查询 Bot
     */
    public PageResult<Bot> pageBots(String ownerType, Long ownerId, String platform, Integer status, int page, int size) {
        LambdaQueryWrapper<Bot> query = new LambdaQueryWrapper<>();

        if (ownerType != null && ownerId != null) {
            query.eq(Bot::getOwnerType, ownerType).eq(Bot::getOwnerId, ownerId);
        }
        if (platform != null && !platform.isEmpty()) {
            query.eq(Bot::getPlatform, platform);
        }
        if (status != null) {
            query.eq(Bot::getStatus, status);
        } else {
            query.eq(Bot::getStatus, 1);
        }

        query.orderByDesc(Bot::getCreateTime);

        Page<Bot> pager = new Page<>(page, size);
        com.baomidou.mybatisplus.core.metadata.IPage<Bot> result = botMapper.selectPage(pager, query);

        return PageResult.of(result.getRecords(), result.getTotal(), page, size);
    }
}
