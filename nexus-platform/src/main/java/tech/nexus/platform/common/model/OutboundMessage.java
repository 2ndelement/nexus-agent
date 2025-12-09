package tech.nexus.platform.common.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 出站消息模型（agent-engine 发出的回复消息）
 * agent-engine 将回复写入 RabbitMQ，nexus-platform 消费后通过对应适配器发送
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class OutboundMessage {

    /**
     * 原始消息ID（对应 PlatformMessage.messageId，用于被动回复）
     */
    private String replyToMessageId;

    /**
     * 平台类型
     */
    private PlatformMessage.PlatformType platform;

    /**
     * 接收者ID（openid / group_openid / channel_id）
     */
    private String targetId;

    /**
     * 会话类型
     */
    private PlatformMessage.ChatType chatType;

    /**
     * 回复内容（文本）
     */
    private String content;

    /**
     * 消息类型（0=文本, 2=markdown）
     */
    private int msgType;
}
