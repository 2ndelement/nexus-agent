package tech.nexus.platform.common.mq;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import tech.nexus.platform.common.model.PlatformMessage;

import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * RabbitMQ 消息队列配置
 * Exchange: nexus.platform.events (topic)
 * Queue: nexus.platform.inbound  - platform → agent-engine
 *        nexus.platform.outbound - agent-engine → platform
 */
@Slf4j
@Configuration
@RequiredArgsConstructor
public class RabbitMQConfig {

    @Value("${nexus.mq.exchange.platform-events:nexus.platform.events}")
    private String exchangeName;

    @Value("${nexus.mq.queue.inbound-messages:nexus.platform.inbound}")
    private String inboundQueueName;

    @Value("${nexus.mq.queue.outbound-messages:nexus.platform.outbound}")
    private String outboundQueueName;

    @Value("${nexus.mq.routing-key.inbound:platform.message.inbound}")
    private String inboundRoutingKey;

    @Value("${nexus.mq.routing-key.outbound:platform.message.outbound}")
    private String outboundRoutingKey;

    // ==================== Exchange ====================

    @Bean
    public TopicExchange platformEventsExchange() {
        return ExchangeBuilder.topicExchange(exchangeName)
                .durable(true)
                .build();
    }

    // ==================== Queues ====================

    /**
     * 入站消息队列：接收用户消息，供 agent-engine 消费
     */
    @Bean
    public Queue inboundMessageQueue() {
        return QueueBuilder.durable(inboundQueueName)
                .withArgument("x-message-ttl", 300000) // 5分钟 TTL
                .build();
    }

    /**
     * 出站消息队列：接收 agent-engine 回复，由 platform 发送给用户
     */
    @Bean
    public Queue outboundMessageQueue() {
        return QueueBuilder.durable(outboundQueueName)
                .withArgument("x-message-ttl", 300000) // 5分钟 TTL
                .build();
    }

    // ==================== Bindings ====================

    @Bean
    public Binding inboundBinding(Queue inboundMessageQueue, TopicExchange platformEventsExchange) {
        return BindingBuilder.bind(inboundMessageQueue)
                .to(platformEventsExchange)
                .with(inboundRoutingKey);
    }

    @Bean
    public Binding outboundBinding(Queue outboundMessageQueue, TopicExchange platformEventsExchange) {
        return BindingBuilder.bind(outboundMessageQueue)
                .to(platformEventsExchange)
                .with(outboundRoutingKey);
    }
}
