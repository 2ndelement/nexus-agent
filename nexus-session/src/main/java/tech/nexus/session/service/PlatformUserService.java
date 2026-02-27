package tech.nexus.session.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import tech.nexus.session.entity.Bot;
import tech.nexus.session.entity.BotBinding;

import java.util.Optional;

/**
 * 平台用户服务
 *
 * 核心功能：通过平台和 puid（平台用户 ID）解析出 Nexus 用户信息。
 *
 * 消息流程：
 * 1. 平台适配器收到消息，提取 puid 和 appId
 * 2. 通过 appId 找到 Bot
 * 3. 通过 Bot + puid 找到 BotBinding
 * 4. 返回 userId 和 Bot 信息
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PlatformUserService {

    private final BotService botService;
    private final BotBindingService botBindingService;

    /**
     * 解析平台用户
     *
     * @param platform 平台类型（QQ, FEISHU, WECHAT 等）
     * @param appId    平台 AppID
     * @param puid     平台用户 ID
     * @return 解析结果
     */
    public PlatformUserResult resolveUser(String platform, String appId, String puid) {
        log.debug("[PlatformUser] 解析用户: platform={}, appId={}, puid={}", platform, appId, puid);

        // 1. 通过 platform + appId 查找 Bot
        Optional<Bot> botOpt = botService.findByPlatformAndAppId(platform, appId);
        if (botOpt.isEmpty()) {
            log.warn("[PlatformUser] Bot 未找到: platform={}, appId={}", platform, appId);
            return PlatformUserResult.notFound("Bot not configured");
        }
        Bot bot = botOpt.get();

        if (bot.getStatus() != 1) {
            log.warn("[PlatformUser] Bot 已禁用: botId={}", bot.getId());
            return PlatformUserResult.notFound("Bot disabled");
        }

        // 2. 通过 botId + puid 查找 Binding
        Optional<BotBinding> bindingOpt = botBindingService.findByBotIdAndPuid(bot.getId(), puid);
        if (bindingOpt.isEmpty()) {
            log.info("[PlatformUser] 用户未绑定: botId={}, puid={}", bot.getId(), puid);
            return PlatformUserResult.notBound(bot, puid);
        }
        BotBinding binding = bindingOpt.get();

        log.info("[PlatformUser] 用户解析成功: botId={}, puid={}, userId={}",
                bot.getId(), puid, binding.getUserId());

        return PlatformUserResult.success(bot, binding.getUserId(), binding.getExtraData());
    }

    /**
     * 绑定平台用户到 Nexus 用户
     */
    public BotBinding bindUser(Long botId, Long userId, String puid) {
        return botBindingService.createOrUpdateBinding(botId, userId, puid, null);
    }

    /**
     * 解析结果
     */
    public static class PlatformUserResult {
        public final boolean success;
        public final boolean bound;         // 是否已绑定
        public final Bot bot;                // Bot 信息
        public final Long userId;           // Nexus 用户 ID
        public final String puid;           // 平台用户 ID
        public final String errorMessage;    // 错误信息

        private PlatformUserResult(boolean success, boolean bound, Bot bot, Long userId, String puid, String errorMessage) {
            this.success = success;
            this.bound = bound;
            this.bot = bot;
            this.userId = userId;
            this.puid = puid;
            this.errorMessage = errorMessage;
        }

        public static PlatformUserResult success(Bot bot, Long userId, String extraData) {
            return new PlatformUserResult(true, true, bot, userId, null, null);
        }

        public static PlatformUserResult notBound(Bot bot, String puid) {
            return new PlatformUserResult(false, false, bot, null, puid, "User not bound");
        }

        public static PlatformUserResult notFound(String message) {
            return new PlatformUserResult(false, false, null, null, null, message);
        }
    }
}
