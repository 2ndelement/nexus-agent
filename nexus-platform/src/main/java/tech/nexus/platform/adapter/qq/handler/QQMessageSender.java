package tech.nexus.platform.adapter.qq.handler;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import tech.nexus.platform.adapter.qq.service.QQMessageService;
import tech.nexus.platform.common.model.PlatformMessage;

/**
 * QQ 消息发送器
 * 
 * 供 MQ 消费者调用，根据 PlatformMessage 发送到对应 QQ 终端。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class QQMessageSender {

    private final QQMessageService qqMessageService;

    /**
     * 发送消息到 QQ
     */
    public void sendMessage(PlatformMessage message) {
        String content = message.getContent();
        if (content == null || content.isBlank()) {
            log.warn("[QQMessage] 消息内容为空，跳过发送");
            return;
        }

        boolean success = qqMessageService.sendReply(message, content);
        if (success) {
            log.info("[QQMessage] 消息发送成功: platform={}, chatId={}", 
                    message.getPlatform(), message.getChatId());
        } else {
            log.error("[QQMessage] 消息发送失败: platform={}, chatId={}", 
                    message.getPlatform(), message.getChatId());
        }
    }
}
