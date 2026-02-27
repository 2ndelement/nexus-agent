package tech.nexus.platform.adapter.webchat.handler;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.*;
import org.springframework.web.socket.handler.TextWebSocketHandler;
import tech.nexus.platform.common.model.PlatformMessage;
import tech.nexus.platform.service.AgentService;

import java.io.IOException;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * WebChat WebSocket 消息处理器
 * 支持心跳检测和断线重连
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class WebChatWebSocketHandler extends TextWebSocketHandler {

    private final ObjectMapper objectMapper;
    private final AgentService agentService;

    /**
     * 活动连接会话 Map: sessionId → WebSocketSession
     */
    private final Map<String, WebSocketSession> activeSessions = new ConcurrentHashMap<>();

    /**
     * 会话元数据 Map: sessionId → metadata
     */
    private final Map<String, SessionMetadata> sessionMetadata = new ConcurrentHashMap<>();

    /**
     * 心跳调度器
     */
    private final ScheduledExecutorService heartbeatScheduler = Executors.newScheduledThreadPool(
            2, r -> {
                Thread t = new Thread(r, "ws-heartbeat");
                t.setDaemon(true);
                return t;
            }
    );

    /**
     * 连接建立
     */
    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws Exception {
        String sessionId = session.getId();
        activeSessions.put(sessionId, session);
        
        // 记录会话元数据
        sessionMetadata.put(sessionId, new SessionMetadata(
                LocalDateTime.now(),
                session.getRemoteAddress() != null ? session.getRemoteAddress().getAddress().getHostAddress() : "unknown"
        ));

        log.info("[WebChat] 新连接建立: sessionId={}, remoteAddr={}",
                sessionId, session.getRemoteAddress());

        // 启动心跳任务
        startHeartbeat(session);

        // 向客户端发送连接成功消息
        sendJson(session, Map.of(
                "type", "connected",
                "sessionId", sessionId,
                "timestamp", LocalDateTime.now().toString()
        ));
    }

    /**
     * 启动心跳 - 定期发送 ping
     */
    private void startHeartbeat(WebSocketSession session) {
        String sessionId = session.getId();
        
        heartbeatScheduler.scheduleAtFixedRate(() -> {
            try {
                if (session.isOpen()) {
                    // 发送 ping
                    sendJson(session, Map.of(
                            "type", "ping",
                            "timestamp", LocalDateTime.now().toString()
                    ));
                    log.debug("[WebChat] 发送心跳: sessionId={}", sessionId);
                } else {
                    // 连接已关闭，停止心跳
                    log.info("[WebChat] 连接已关闭，停止心跳: sessionId={}", sessionId);
                    activeSessions.remove(sessionId);
                    sessionMetadata.remove(sessionId);
                }
            } catch (Exception e) {
                log.error("[WebChat] 心跳发送失败: sessionId={}, error={}", sessionId, e.getMessage());
            }
        }, 30, 30, TimeUnit.SECONDS); // 30秒心跳间隔
    }

    /**
     * 接收文本消息
     */
    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage textMessage) throws Exception {
        String payload = textMessage.getPayload();
        String sessionId = session.getId();
        
        log.debug("[WebChat] 收到消息: sessionId={}, payload={}", sessionId, payload);

        // 更新最后活跃时间
        SessionMetadata metadata = sessionMetadata.get(sessionId);
        if (metadata != null) {
            metadata.setLastActiveTime(LocalDateTime.now());
        }

        try {
            JsonNode node = objectMapper.readTree(payload);
            String type = node.path("type").asText("message");

            switch (type) {
                case "ping" -> handlePing(session);
                case "pong" -> handlePong(session);  // 处理客户端pong
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
     * 处理客户端 pong 响应
     */
    private void handlePong(WebSocketSession session) {
        log.debug("[WebChat] 收到客户端 pong: sessionId={}", session.getId());
    }

    /**
     * 处理身份认证消息
     */
    private void handleIdentify(WebSocketSession session, JsonNode node) throws IOException {
        String tenantId = node.path("tenantId").asText(null);
        String userId = node.path("userId").asText(null);
        
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
        // WebChat 轻量集成：使用默认 Web Bot (id=1)
        PlatformMessage message = PlatformMessage.builder()
                .messageId(messageId)
                .platform(PlatformMessage.PlatformType.WEB)
                .messageType(PlatformMessage.MessageType.TEXT)
                .chatType(PlatformMessage.ChatType.PRIVATE)
                .senderId(userId)
                .chatId(chatId)
                .content(content)
                .tenantId(tenantId)
                .botId(1L)  // 默认 Web Bot
                .puid(userId)  // Web 用户直接使用 userId 作为平台身份
                .rawPayload(node.toString())
                .receivedAt(LocalDateTime.now())
                .build();

        // 返回确认
        sendJson(session, Map.of(
                "type", "ack",
                "messageId", messageId,
                "status", "processing",
                "timestamp", LocalDateTime.now().toString()
        ));

        // 调用 AgentService 流式推送
        agentService.streamChatToWebSocket(message, session);
    }

    /**
     * 连接关闭
     */
    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        String sessionId = session.getId();
        activeSessions.remove(sessionId);
        sessionMetadata.remove(sessionId);
        log.info("[WebChat] 连接关闭: sessionId={}, status={}", sessionId, status);
    }

    /**
     * 传输错误
     */
    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) {
        log.error("[WebChat] 传输错误: sessionId={}, error={}", session.getId(), exception.getMessage());
        activeSessions.remove(session.getId());
        sessionMetadata.remove(session.getId());
    }

    /**
     * 向指定会话发送消息
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

    /**
     * 会话元数据
     */
    private static class SessionMetadata {
        private LocalDateTime lastActiveTime;
        private String remoteAddress;

        public SessionMetadata(LocalDateTime lastActiveTime, String remoteAddress) {
            this.lastActiveTime = lastActiveTime;
            this.remoteAddress = remoteAddress;
        }

        public LocalDateTime getLastActiveTime() {
            return lastActiveTime;
        }

        public void setLastActiveTime(LocalDateTime lastActiveTime) {
            this.lastActiveTime = lastActiveTime;
        }

        public String getRemoteAddress() {
            return remoteAddress;
        }
    }
}
