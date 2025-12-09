package tech.nexus.platform.adapter.webchat.controller;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import tech.nexus.platform.adapter.webchat.handler.WebChatWebSocketHandler;
import tech.nexus.platform.common.model.PlatformMessage;
import tech.nexus.platform.common.mq.PlatformMessagePublisher;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;

/**
 * WebChat REST API Controller
 * <p>
 * 提供 HTTP 接口用于：
 * 1. 健康检查
 * 2. 查询活跃连接数
 * 3. 通过 REST 发送消息（适用于非 WebSocket 场景）
 * 4. 向指定 WebSocket 会话推送消息（供 agent-engine 回调）
 */
@Slf4j
@RestController
@RequestMapping("/api/platform/webchat")
@RequiredArgsConstructor
public class WebChatController {

    private final WebChatWebSocketHandler webSocketHandler;
    private final PlatformMessagePublisher messagePublisher;

    /**
     * 健康检查 + 活跃连接数
     */
    @GetMapping("/status")
    public ResponseEntity<Map<String, Object>> status() {
        return ResponseEntity.ok(Map.of(
                "status", "ok",
                "adapter", "webchat",
                "activeSessions", webSocketHandler.getActiveSessionCount(),
                "timestamp", LocalDateTime.now().toString()
        ));
    }

    /**
     * 通过 REST 发送消息（非 WebSocket 场景）
     * POST /api/platform/webchat/messages
     */
    @PostMapping("/messages")
    public ResponseEntity<Map<String, Object>> sendMessage(@Valid @RequestBody WebChatMessageRequest request) {
        String messageId = UUID.randomUUID().toString();

        PlatformMessage message = PlatformMessage.builder()
                .messageId(messageId)
                .platform(PlatformMessage.PlatformType.WEBCHAT)
                .messageType(PlatformMessage.MessageType.TEXT)
                .chatType(PlatformMessage.ChatType.PRIVATE)
                .senderId(request.userId())
                .chatId(request.chatId() != null ? request.chatId() : request.userId())
                .content(request.content())
                .tenantId(request.tenantId())
                .receivedAt(LocalDateTime.now())
                .build();

        messagePublisher.publishInboundMessage(message);
        log.info("[WebChat REST] 消息已发布: messageId={}, userId={}", messageId, request.userId());

        return ResponseEntity.ok(Map.of(
                "messageId", messageId,
                "status", "queued"
        ));
    }

    /**
     * 向指定 WebSocket 会话推送回复（由 agent-engine 通过内部 HTTP 调用）
     * POST /api/platform/webchat/sessions/{sessionId}/push
     */
    @PostMapping("/sessions/{sessionId}/push")
    public ResponseEntity<Map<String, Object>> pushToSession(
            @PathVariable String sessionId,
            @RequestBody Map<String, String> body) {
        String content = body.get("content");
        if (content == null || content.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "content 不能为空"));
        }
        webSocketHandler.sendToSession(sessionId, content);
        return ResponseEntity.ok(Map.of("status", "sent", "sessionId", sessionId));
    }

    // ==================== Request Records ====================

    record WebChatMessageRequest(
            @NotBlank String userId,
            String chatId,
            @NotBlank String content,
            String tenantId
    ) {}
}
