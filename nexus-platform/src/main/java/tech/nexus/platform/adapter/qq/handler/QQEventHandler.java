package tech.nexus.platform.adapter.qq.handler;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import tech.nexus.platform.common.model.PlatformMessage;
import tech.nexus.platform.common.mq.PlatformMessagePublisher;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * QQ 机器人事件处理器
 * <p>
 * 负责将 QQ WebSocket 推送的事件（op=0，Dispatch 事件）
 * 转换为统一 PlatformMessage 并发布到 RabbitMQ
 * <p>
 * 支持的事件类型：
 * - AT_MESSAGE_CREATE      : 频道@机器人消息
 * - MESSAGE_CREATE         : 频道私域消息
 * - DIRECT_MESSAGE_CREATE  : 频道私信消息
 * - GROUP_AT_MESSAGE_CREATE: 群聊@机器人消息
 * - C2C_MESSAGE_CREATE     : 用户单聊消息
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class QQEventHandler {

    private final ObjectMapper objectMapper;
    private final PlatformMessagePublisher messagePublisher;

    /**
     * 处理 QQ 事件（由 QQGatewayClient 调用）
     *
     * @param eventType 事件类型（t 字段）
     * @param data      事件数据（d 字段）
     */
    public void handleEvent(String eventType, JsonNode data) {
        log.debug("[QQEvent] 收到事件: type={}", eventType);
        try {
            switch (eventType) {
                case "AT_MESSAGE_CREATE" -> handleAtMessage(data, PlatformMessage.PlatformType.QQ_GUILD);
                case "MESSAGE_CREATE" -> handleAtMessage(data, PlatformMessage.PlatformType.QQ_GUILD);
                case "DIRECT_MESSAGE_CREATE" -> handleDirectMessage(data);
                case "GROUP_AT_MESSAGE_CREATE" -> handleGroupAtMessage(data);
                case "C2C_MESSAGE_CREATE" -> handleC2CMessage(data);
                default -> log.debug("[QQEvent] 忽略未处理事件: type={}", eventType);
            }
        } catch (Exception e) {
            log.error("[QQEvent] 事件处理失败: type={}, error={}", eventType, e.getMessage(), e);
        }
    }

    /**
     * 频道@机器人消息
     */
    private void handleAtMessage(JsonNode data, PlatformMessage.PlatformType platformType) {
        String messageId = data.path("id").asText(UUID.randomUUID().toString());
        String content = cleanAtContent(data.path("content").asText(""));
        String channelId = data.path("channel_id").asText();
        String guildId = data.path("guild_id").asText();
        String authorId = data.path("author").path("id").asText();
        String authorName = data.path("author").path("username").asText();

        PlatformMessage message = PlatformMessage.builder()
                .messageId(messageId)
                .platform(platformType)
                .messageType(PlatformMessage.MessageType.AT)
                .chatType(PlatformMessage.ChatType.CHANNEL)
                .senderId(authorId)
                .senderName(authorName)
                .chatId(channelId)
                .content(content)
                .rawPayload(data.toString())
                .receivedAt(LocalDateTime.now())
                .build();

        messagePublisher.publishInboundMessage(message);
        log.info("[QQEvent] AT消息已处理: channelId={}, authorId={}, content={}",
                channelId, authorId, content);
    }

    /**
     * 频道私信消息
     */
    private void handleDirectMessage(JsonNode data) {
        String messageId = data.path("id").asText(UUID.randomUUID().toString());
        String content = data.path("content").asText("").trim();
        String guildId = data.path("guild_id").asText();
        String authorId = data.path("author").path("id").asText();
        String authorName = data.path("author").path("username").asText();

        PlatformMessage message = PlatformMessage.builder()
                .messageId(messageId)
                .platform(PlatformMessage.PlatformType.QQ_GUILD_DM)
                .messageType(PlatformMessage.MessageType.TEXT)
                .chatType(PlatformMessage.ChatType.PRIVATE)
                .senderId(authorId)
                .senderName(authorName)
                .chatId(guildId)
                .content(content)
                .rawPayload(data.toString())
                .receivedAt(LocalDateTime.now())
                .build();

        messagePublisher.publishInboundMessage(message);
        log.info("[QQEvent] 频道私信已处理: guildId={}, authorId={}", guildId, authorId);
    }

    /**
     * 群聊@机器人消息
     */
    private void handleGroupAtMessage(JsonNode data) {
        String messageId = data.path("id").asText(UUID.randomUUID().toString());
        String content = cleanAtContent(data.path("content").asText(""));
        String groupOpenId = data.path("group_openid").asText();
        String authorOpenId = data.path("author").path("member_openid").asText();

        PlatformMessage message = PlatformMessage.builder()
                .messageId(messageId)
                .platform(PlatformMessage.PlatformType.QQ_GROUP)
                .messageType(PlatformMessage.MessageType.AT)
                .chatType(PlatformMessage.ChatType.GROUP)
                .senderId(authorOpenId)
                .chatId(groupOpenId)
                .content(content)
                .rawPayload(data.toString())
                .receivedAt(LocalDateTime.now())
                .build();

        messagePublisher.publishInboundMessage(message);
        log.info("[QQEvent] 群聊AT消息已处理: groupOpenId={}, authorOpenId={}",
                groupOpenId, authorOpenId);
    }

    /**
     * 单聊消息 (C2C)
     */
    private void handleC2CMessage(JsonNode data) {
        String messageId = data.path("id").asText(UUID.randomUUID().toString());
        String content = data.path("content").asText("").trim();
        String userOpenId = data.path("author").path("user_openid").asText();

        PlatformMessage message = PlatformMessage.builder()
                .messageId(messageId)
                .platform(PlatformMessage.PlatformType.QQ)
                .messageType(PlatformMessage.MessageType.TEXT)
                .chatType(PlatformMessage.ChatType.PRIVATE)
                .senderId(userOpenId)
                .chatId(userOpenId)
                .content(content)
                .rawPayload(data.toString())
                .receivedAt(LocalDateTime.now())
                .build();

        messagePublisher.publishInboundMessage(message);
        log.info("[QQEvent] 单聊消息已处理: userOpenId={}", userOpenId);
    }

    /**
     * 清理@机器人的内容（去除 <@!botId> 前缀和首尾空白）
     */
    private String cleanAtContent(String content) {
        if (content == null) return "";
        // 去除 <@!xxx> 或 <@xxx> 格式的 @ 提及
        return content.replaceAll("<@!?\\d+>", "").trim();
    }
}
