package tech.nexus.platform.adapter.qq.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import tech.nexus.platform.adapter.qq.config.QQBotProperties;
import tech.nexus.platform.common.model.PlatformMessage;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

/**
 * QQ 消息发送服务
 * <p>
 * 通过 HTTP API 向 QQ 用户/群组/频道发送消息
 * API v2 文档: https://bot.q.qq.com/wiki/develop/api-v2/
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class QQMessageService {

    private final QQBotProperties properties;
    private final QQTokenService tokenService;
    private final ObjectMapper objectMapper;

    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    /**
     * 发送单聊消息 (C2C)
     * POST /v2/users/{openid}/messages
     *
     * @param userOpenId 用户 openid
     * @param content    消息文本
     * @param replyMsgId 被动回复的原消息ID（24小时内有效）
     */
    public boolean sendC2CMessage(String userOpenId, String content, String replyMsgId) {
        String url = properties.getApiBaseUrl() + "/v2/users/" + userOpenId + "/messages";
        Map<String, Object> body = buildTextMessageBody(content, replyMsgId);
        return doPost(url, body, "C2C消息");
    }

    /**
     * 发送群聊消息
     * POST /v2/groups/{group_openid}/messages
     *
     * @param groupOpenId 群 openid
     * @param content     消息文本
     * @param replyMsgId  被动回复的原消息ID
     */
    public boolean sendGroupMessage(String groupOpenId, String content, String replyMsgId) {
        String url = properties.getApiBaseUrl() + "/v2/groups/" + groupOpenId + "/messages";
        Map<String, Object> body = buildTextMessageBody(content, replyMsgId);
        return doPost(url, body, "群聊消息");
    }

    /**
     * 发送频道消息（子频道）
     * POST /channels/{channel_id}/messages
     *
     * @param channelId  子频道ID
     * @param content    消息文本
     * @param replyMsgId 被动回复的原消息ID
     */
    public boolean sendChannelMessage(String channelId, String content, String replyMsgId) {
        String url = properties.getApiBaseUrl() + "/channels/" + channelId + "/messages";
        Map<String, Object> body = buildTextMessageBody(content, replyMsgId);
        return doPost(url, body, "频道消息");
    }

    /**
     * 发送频道私信
     * POST /dms/{guild_id}/messages
     *
     * @param guildId    频道 guild_id（私信会话 ID）
     * @param content    消息文本
     * @param replyMsgId 被动回复的原消息ID
     */
    public boolean sendDirectMessage(String guildId, String content, String replyMsgId) {
        String url = properties.getApiBaseUrl() + "/dms/" + guildId + "/messages";
        Map<String, Object> body = buildTextMessageBody(content, replyMsgId);
        return doPost(url, body, "频道私信");
    }

    /**
     * 根据 PlatformMessage 路由发送回复消息
     *
     * @param originalMessage 原始消息（含平台类型、chatId 等路由信息）
     * @param replyContent    回复内容
     */
    public boolean sendReply(PlatformMessage originalMessage, String replyContent) {
        String chatId = originalMessage.getChatId();
        String messageId = originalMessage.getMessageId();

        return switch (originalMessage.getPlatform()) {
            case QQ -> sendC2CMessage(chatId, replyContent, messageId);
            case QQ_GROUP -> sendGroupMessage(chatId, replyContent, messageId);
            case QQ_GUILD -> sendChannelMessage(chatId, replyContent, messageId);
            case QQ_GUILD_DM -> sendDirectMessage(chatId, replyContent, messageId);
            default -> {
                log.warn("[QQMessage] 不支持的平台类型: {}", originalMessage.getPlatform());
                yield false;
            }
        };
    }

    // ==================== 私有工具方法 ====================

    private Map<String, Object> buildTextMessageBody(String content, String replyMsgId) {
        Map<String, Object> body = new HashMap<>();
        body.put("msg_type", 0); // 0 = 纯文本
        body.put("content", content);
        if (replyMsgId != null && !replyMsgId.isBlank()) {
            body.put("msg_id", replyMsgId);
        }
        return body;
    }

    private boolean doPost(String url, Map<String, Object> body, String scene) {
        try {
            String requestBody = objectMapper.writeValueAsString(body);
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .header("Content-Type", "application/json")
                    .header("Authorization", tokenService.getAuthorizationHeader())
                    .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                    .timeout(Duration.ofSeconds(15))
                    .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() == 200 || response.statusCode() == 201 || response.statusCode() == 202) {
                log.info("[QQMessage] {}发送成功: url={}", scene, url);
                return true;
            } else {
                log.error("[QQMessage] {}发送失败: url={}, status={}, body={}",
                        scene, url, response.statusCode(), response.body());
                return false;
            }
        } catch (Exception e) {
            log.error("[QQMessage] {}发送异常: url={}, error={}", scene, url, e.getMessage(), e);
            return false;
        }
    }
}
