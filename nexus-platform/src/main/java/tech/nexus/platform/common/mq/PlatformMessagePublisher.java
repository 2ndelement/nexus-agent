package tech.nexus.platform.common.mq;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import tech.nexus.platform.common.model.PlatformMessage;

/**
 * 消息发布者 - 将平台接收到的消息发布到 RabbitMQ 入站队列
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class PlatformMessagePublisher {

    private final RabbitTemplate rabbitTemplate;
    private final ObjectMapper objectMapper;

    @Value("${nexus.mq.exchange.platform-events:nexus.platform.events}")
    private String exchangeName;

    @Value("${nexus.mq.routing-key.inbound:platform.message.inbound}")
    private String inboundRoutingKey;

    /**
     * 发布用户消息到入站队列
     *
     * @param message 统一平台消息
     */
    public void publishInboundMessage(PlatformMessage message) {
        try {
            String json = objectMapper.writeValueAsString(message);
            rabbitTemplate.convertAndSend(exchangeName, inboundRoutingKey, json);
            log.info("[MQ] 入站消息已发布: platform={}, chatId={}, senderId={}",
                    message.getPlatform(), message.getChatId(), message.getSenderId());
        } catch (Exception e) {
            log.error("[MQ] 入站消息发布失败: {}", e.getMessage(), e);
        }
    }
}
