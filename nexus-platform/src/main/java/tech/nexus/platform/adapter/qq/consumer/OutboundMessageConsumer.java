package tech.nexus.platform.adapter.qq.consumer;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;
import tech.nexus.platform.adapter.qq.handler.QQMessageSender;
import tech.nexus.platform.common.model.PlatformMessage;

/**
 * MQ 出站消息消费者
 * 
 * 监听 nexus.platform.outbound 队列，消费 agent-engine 返回的消息，
 * 根据平台类型发送到对应的终端（QQ/WebSocket 等）。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class OutboundMessageConsumer {

    private final ObjectMapper objectMapper;
    private final QQMessageSender qqMessageSender;

    /**
     * 监听出站消息队列
     */
    @RabbitListener(queues = "${nexus.mq.queue.outbound-messages:nexus.platform.outbound}")
    public void handleOutboundMessage(String messageJson) {
        try {
            PlatformMessage message = objectMapper.readValue(messageJson, PlatformMessage.class);
            log.info("[MQ] 收到出站消息: platform={}, chatId={}, content={}",
                    message.getPlatform(), message.getChatId(), 
                    message.getContent() != null ? message.getContent().substring(0, Math.min(50, message.getContent().length())) : "");

            // 根据平台类型分发
            switch (message.getPlatform()) {
                case QQ, QQ_GROUP, QQ_GUILD, QQ_GUILD_DM -> {
                    // 发送到 QQ
                    qqMessageSender.sendMessage(message);
                }
                case WEBCHAT -> {
                    // WebChat 通过 WebSocket 发送（由 WebChatWebSocketHandler 直接处理）
                    // 这里暂时不处理，留给 WebSocketHandler
                    log.debug("[MQ] WebChat 消息不做处理，由 WebSocket 直连处理");
                }
                default -> {
                    log.warn("[MQ] 未知平台类型: {}", message.getPlatform());
                }
            }

        } catch (Exception e) {
            log.error("[MQ] 处理出站消息失败: {}", e.getMessage(), e);
        }
    }
}
