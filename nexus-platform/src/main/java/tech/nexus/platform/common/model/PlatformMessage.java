package tech.nexus.platform.common.model;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 统一平台消息模型
 * 所有适配器接收到的消息都转换为此格式，发送到 RabbitMQ 供 agent-engine 消费
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PlatformMessage {

    /**
     * 消息唯一ID（由平台分配）
     */
    private String messageId;

    /**
     * 平台类型
     */
    private PlatformType platform;

    /**
     * 消息类型
     */
    private MessageType messageType;

    /**
     * 会话类型（私聊/群聊/频道）
     */
    private ChatType chatType;

    /**
     * 发送者ID（平台用户 openid）
     */
    private String senderId;

    /**
     * 发送者昵称（可选）
     */
    private String senderName;

    /**
     * 会话ID（群ID/频道ID/私聊则等于 senderId）
     */
    private String chatId;

    /**
     * 消息文本内容
     */
    private String content;

    /**
     * 原始消息 JSON（用于回复时的 msg_seq 等）
     */
    private String rawPayload;

    /**
     * 租户ID（平台级别可能为 null，由 agent-engine 路由时填充）
     */
    private String tenantId;

    /**
     * 消息接收时间
     */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime receivedAt;

    /**
     * 平台类型枚举
     */
    public enum PlatformType {
        WEBCHAT,    // Web 网页聊天
        QQ,         // QQ 单聊
        QQ_GROUP,   // QQ 群聊
        QQ_GUILD,   // QQ 频道
        QQ_GUILD_DM // QQ 频道私信
    }

    /**
     * 消息类型枚举
     */
    public enum MessageType {
        TEXT,       // 纯文本
        IMAGE,      // 图片
        AUDIO,      // 语音
        VIDEO,      // 视频
        FILE,       // 文件
        AT,         // @消息
        MIXED       // 混合消息
    }

    /**
     * 会话类型枚举
     */
    public enum ChatType {
        PRIVATE,    // 私聊
        GROUP,      // 群聊
        CHANNEL     // 频道
    }
}
