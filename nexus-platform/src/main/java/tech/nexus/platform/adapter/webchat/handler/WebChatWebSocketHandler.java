package tech.nexus.platform.adapter.webchat.handler;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.*;
import org.springframework.web.socket.handler.TextWebSocketHandler;
import tech.nexus.platform.common.model.PlatformMessage;
import tech.nexus.platform.common.mq.PlatformMessagePublisher;

import java.io.IOException;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * WebChat WebSocket 消息处理器
 * <p>
 * 协议规范（客户端 → 服务端）：
 * <pre>
 * {
 *   "type": "message",      // message | ping | identify
 *   "content": "用户消息",
 *   "sessionId": "xxx",     // 可选，会话标识
 *   "tenantId": "xxx"       // 租户ID（由前端从 JWT 中解析后传入）
 * }
 * </pre>
 * <p>
 * 协议规范（服务端 → 客户端）：
 * <pre>
 * {
 *   "type": "message" | "reply" | "error" | "pong" | "connected",
 *   "messageId": "xxx",
 *   "content": "...",
 *   "timestamp": "..."
 * }
 * </pre>
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class WebChatWebSocketHandler extends TextWebSocketHandler {

    private final ObjectMapper objectMapper;
    private final PlatformMessagePublisher messagePublisher;

    /**
     * 活跃连接会话 Map: sessionId → WebSocketSession
     */
    private final Map<String, WebSocketSession> activeSessions = new ConcurrentHashMap<>();

    /**
     * 连接建立
     */
    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws Exception {
        String sessionId = session.getId();
        activeSessions.put(sessionId, session);
        log.info("[WebChat] 新连接建立: sessionId={}, remoteAddr={}",
                sessionId, session.getRemoteAddress());

        // 向客户端发送连接成功消息
        sendJson(session, Map.of(
                "type", "connected",
                "sessionId", sessionId,
                "timestamp", LocalDateTime.now().toString()
        ));
    }

    /**
     * 接收文本消息
     */
    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage textMessage) throws Exception {
        String payload = textMessage.getPayload();
        log.debug("[WebChat] 收到消息: sessionId={}, payload={}", session.getId(), payload);

        try {
            JsonNode node = objectMapper.readTree(payload);
            String type = node.path("type").asText("message");

            switch (type) {
                case "ping" -> handlePing(session);
                case "identify" -> handleIdentify(session, node);
                case "message" -> handleChatMessage(session, node);
                default -> {
                    log.warn("[WebChat] 未知消息类型: type={}", type);
                    sendError(session, "未知消息类型: " + type);
                }
            }
        } catch (Exception e) {
            log.error("[WebChat] 消息处理异常: {}", e.getMessage(), e);
            sendError(session, "消息格式错误: " + e.getMessage());
        }
    }

    /**
     * 处理 ping 心跳
     */
    private void handlePing(WebSocketSession session) throws IOException {
        sendJson(session, Map.of("type", "pong", "timestamp", LocalDateTime.now().toString()));
    }

    /**
     * 处理身份认证消息（客户端传入 tenantId/userId）
     */
    private void handleIdentify(WebSocketSession session, JsonNode node) throws IOException {
        String tenantId = node.path("tenantId").asText(null);
        String userId = node.path("userId").asText(null);
        // 将元数据存入 session attributes
        session.getAttributes().put("tenantId", tenantId);
        session.getAttributes().put("userId", userId);
        log.info("[WebChat] 用户身份确认: sessionId={}, tenantId={}, userId={}",
                session.getId(), tenantId, userId);
        sendJson(session, Map.of("type", "identified", "status", "ok"));
    }

    /**
     * 处理聊天消息
     */
    private void handleChatMessage(WebSocketSession session, JsonNode node) throws IOException {
        String content = node.path("content").asText("").trim();
        if (content.isEmpty()) {
            sendError(session, "消息内容不能为空");
            return;
        }

        String tenantId = (String) session.getAttributes().getOrDefault("tenantId",
                node.path("tenantId").asText(null));
        String userId = (String) session.getAttributes().getOrDefault("userId",
                node.path("userId").asText(session.getId()));
        String chatId = node.path("chatId").asText(session.getId());
        String messageId = UUID.randomUUID().toString();

        // 构建统一消息格式
        PlatformMessage message = PlatformMessage.builder()
                .messageId(messageId)
                .platform(PlatformMessage.PlatformType.WEBCHAT)
                .messageType(PlatformMessage.MessageType.TEXT)
                .chatType(PlatformMessage.ChatType.PRIVATE)
                .senderId(userId)
                .chatId(chatId)
                .content(content)
                .tenantId(tenantId)
                .rawPayload(node.toString())
                .receivedAt(LocalDateTime.now())
                .build();

        // 发布到消息队列
        messagePublisher.publishInboundMessage(message);

        // 回复确认
        sendJson(session, Map.of(
                "type", "ack",
                "messageId", messageId,
                "status", "queued",
                "timestamp", LocalDateTime.now().toString()
        ));
    }

    /**
     * 连接关闭
     */
    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        activeSessions.remove(session.getId());
        log.info("[WebChat] 连接关闭: sessionId={}, status={}", session.getId(), status);
    }

    /**
     * 传输错误
     */
    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) {
        log.error("[WebChat] 传输错误: sessionId={}, error={}", session.getId(), exception.getMessage());
        activeSessions.remove(session.getId());
    }

    /**
     * 向指定会话发送消息（供 OutboundMessageConsumer 调用）
     */
    public void sendToSession(String sessionId, String content) {
        WebSocketSession session = activeSessions.get(sessionId);
        if (session == null || !session.isOpen()) {
            log.warn("[WebChat] 目标会话不存在或已关闭: sessionId={}", sessionId);
            return;
        }
        try {
            sendJson(session, Map.of(
                    "type", "reply",
                    "content", content,
                    "timestamp", LocalDateTime.now().toString()
            ));
        } catch (IOException e) {
            log.error("[WebChat] 发送消息失败: sessionId={}, error={}", sessionId, e.getMessage());
        }
    }

    /**
     * 获取当前活跃连接数
     */
    public int getActiveSessionCount() {
        return activeSessions.size();
    }

    // ==================== 私有工具方法 ====================

    private void sendJson(WebSocketSession session, Object data) throws IOException {
        if (session.isOpen()) {
            String json = objectMapper.writeValueAsString(data);
            session.sendMessage(new TextMessage(json));
        }
    }

    private void sendError(WebSocketSession session, String errorMsg) throws IOException {
        sendJson(session, Map.of("type", "error", "message", errorMsg));
    }
}
