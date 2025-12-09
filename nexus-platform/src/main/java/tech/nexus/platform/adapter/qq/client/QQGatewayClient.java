package tech.nexus.platform.adapter.qq.client;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.websocket.*;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;
import tech.nexus.platform.adapter.qq.config.QQBotProperties;
import tech.nexus.platform.adapter.qq.handler.QQEventHandler;
import tech.nexus.platform.adapter.qq.service.QQTokenService;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * QQ Bot WebSocket Gateway 客户端
 * <p>
 * 实现 QQ 机器人 WebSocket 接入流程：
 * 1. 获取 Gateway 地址
 * 2. 建立 WSS 长连接
 * 3. 收到 Hello (op=10)，记录 heartbeat_interval
 * 4. 发送鉴权 (op=2)
 * 5. 收到 Ready (op=0, t="READY")，连接成功
 * 6. 定时心跳 (op=1)
 * 7. 自动断线重连
 */
@Slf4j
@Component
@ClientEndpoint
public class QQGatewayClient {

    @Autowired
    private QQBotProperties properties;

    @Autowired
    private QQTokenService tokenService;

    @Autowired
    private QQEventHandler eventHandler;

    @Autowired
    private ObjectMapper objectMapper;

    // WebSocket 操作码
    private static final int OP_DISPATCH = 0;       // 事件推送
    private static final int OP_HEARTBEAT = 1;      // 心跳
    private static final int OP_IDENTIFY = 2;       // 鉴权
    private static final int OP_RESUME = 6;         // 恢复连接
    private static final int OP_RECONNECT = 7;      // 服务端要求重连
    private static final int OP_INVALID_SESSION = 9; // 无效 Session
    private static final int OP_HELLO = 10;         // 服务端发送心跳间隔
    private static final int OP_HEARTBEAT_ACK = 11; // 心跳 ACK

    private volatile Session wsSession;
    private volatile boolean connected = false;
    private volatile int heartbeatInterval = 45000; // 默认45秒
    private volatile Integer lastSeq = null;        // 最新事件序列号（用于心跳和恢复）
    private volatile String sessionId;              // Gateway 分配的 session_id

    private final AtomicInteger reconnectAttempts = new AtomicInteger(0);
    private final ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(2);
    private volatile ScheduledFuture<?> heartbeatTask;

    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    /**
     * Spring 应用就绪后自动启动（仅在 qq.enabled=true 时）
     */
    @EventListener(ApplicationReadyEvent.class)
    public void onApplicationReady() {
        if (!properties.isEnabled()) {
            log.info("[QQGateway] QQ机器人适配器已禁用（qq.enabled=false），跳过启动");
            return;
        }
        if (properties.getAppId() == null || properties.getAppId().isBlank()) {
            log.warn("[QQGateway] QQ_APP_ID 未配置，跳过启动");
            return;
        }
        log.info("[QQGateway] 启动 QQ 机器人适配器, appId={}", properties.getAppId());
        connect();
    }

    /**
     * 建立 WebSocket 连接
     */
    public void connect() {
        scheduler.execute(() -> {
            try {
                String gatewayUrl = properties.getGatewayUrl();
                log.info("[QQGateway] 连接 Gateway: {}", gatewayUrl);

                WebSocketContainer container = ContainerProvider.getWebSocketContainer();
                container.setDefaultMaxTextMessageBufferSize(65536);
                container.connectToServer(this, URI.create(gatewayUrl));
            } catch (Exception e) {
                log.error("[QQGateway] 连接失败: {}", e.getMessage(), e);
                scheduleReconnect();
            }
        });
    }

    // ==================== WebSocket 生命周期 ====================

    @OnOpen
    public void onOpen(Session session) {
        this.wsSession = session;
        this.connected = true;
        this.reconnectAttempts.set(0);
        log.info("[QQGateway] WebSocket 连接已建立: sessionId={}", session.getId());
    }

    @OnMessage
    public void onMessage(String message) {
        try {
            JsonNode payload = objectMapper.readTree(message);
            int op = payload.path("op").asInt(-1);
            JsonNode data = payload.path("d");

            // 更新序列号
            if (!payload.path("s").isNull() && payload.path("s").isInt()) {
                lastSeq = payload.path("s").asInt();
            }

            switch (op) {
                case OP_HELLO -> handleHello(data);
                case OP_DISPATCH -> handleDispatch(payload);
                case OP_HEARTBEAT_ACK -> log.debug("[QQGateway] 心跳 ACK 收到");
                case OP_RECONNECT -> handleReconnect();
                case OP_INVALID_SESSION -> handleInvalidSession();
                default -> log.debug("[QQGateway] 收到未处理 op: {}", op);
            }
        } catch (Exception e) {
            log.error("[QQGateway] 消息处理异常: {}", e.getMessage(), e);
        }
    }

    @OnClose
    public void onClose(Session session, CloseReason reason) {
        this.connected = false;
        stopHeartbeat();
        log.warn("[QQGateway] WebSocket 连接关闭: reason={}", reason);
        scheduleReconnect();
    }

    @OnError
    public void onError(Session session, Throwable error) {
        log.error("[QQGateway] WebSocket 错误: {}", error.getMessage(), error);
        this.connected = false;
        stopHeartbeat();
    }

    // ==================== 协议处理 ====================

    /**
     * 处理 Hello (op=10)，获取心跳间隔，发送鉴权
     */
    private void handleHello(JsonNode data) {
        this.heartbeatInterval = data.path("heartbeat_interval").asInt(45000);
        log.info("[QQGateway] 收到 Hello, heartbeatInterval={}ms", heartbeatInterval);
        startHeartbeat();
        sendIdentify();
    }

    /**
     * 发送鉴权 (op=2)
     */
    private void sendIdentify() {
        try {
            String token = tokenService.getAccessToken();
            Map<String, Object> identifyData = Map.of(
                    "token", "QQBot " + token,
                    "intents", properties.getIntents(),
                    "shard", new int[]{0, 1},
                    "properties", Map.of(
                            "$os", "linux",
                            "$browser", "nexus-platform",
                            "$device", "nexus-platform"
                    )
            );
            Map<String, Object> payload = Map.of("op", OP_IDENTIFY, "d", identifyData);
            sendMessage(objectMapper.writeValueAsString(payload));
            log.info("[QQGateway] 鉴权消息已发送, intents={}", properties.getIntents());
        } catch (Exception e) {
            log.error("[QQGateway] 发送鉴权失败: {}", e.getMessage(), e);
        }
    }

    /**
     * 处理 Dispatch 事件 (op=0)
     */
    private void handleDispatch(JsonNode payload) {
        String eventType = payload.path("t").asText();
        JsonNode data = payload.path("d");

        if ("READY".equals(eventType)) {
            this.sessionId = data.path("session_id").asText();
            String username = data.path("user").path("username").asText();
            log.info("[QQGateway] 连接就绪! botName={}, sessionId={}", username, sessionId);
            return;
        }

        if ("RESUMED".equals(eventType)) {
            log.info("[QQGateway] 连接已恢复");
            return;
        }

        // 转发到事件处理器
        eventHandler.handleEvent(eventType, data);
    }

    /**
     * 处理服务端要求重连 (op=7)
     */
    private void handleReconnect() {
        log.warn("[QQGateway] 服务端要求重连");
        closeConnection();
        scheduleReconnect();
    }

    /**
     * 处理无效 Session (op=9)
     */
    private void handleInvalidSession() {
        log.warn("[QQGateway] Session 无效，清除 sessionId 后重连");
        this.sessionId = null;
        this.lastSeq = null;
        closeConnection();
        scheduleReconnect();
    }

    // ==================== 心跳管理 ====================

    /**
     * 启动定时心跳
     */
    private void startHeartbeat() {
        stopHeartbeat();
        long intervalMs = (long) (heartbeatInterval * properties.getHeartbeatRatio());
        heartbeatTask = scheduler.scheduleAtFixedRate(
                this::sendHeartbeat,
                intervalMs,
                intervalMs,
                TimeUnit.MILLISECONDS
        );
        log.info("[QQGateway] 心跳已启动, interval={}ms", intervalMs);
    }

    /**
     * 发送心跳 (op=1)
     */
    private void sendHeartbeat() {
        try {
            Map<String, Object> payload = Map.of("op", OP_HEARTBEAT, "d", lastSeq != null ? lastSeq : "null");
            sendMessage(objectMapper.writeValueAsString(payload));
            log.debug("[QQGateway] 心跳已发送, seq={}", lastSeq);
        } catch (Exception e) {
            log.error("[QQGateway] 发送心跳失败: {}", e.getMessage(), e);
        }
    }

    private void stopHeartbeat() {
        if (heartbeatTask != null && !heartbeatTask.isCancelled()) {
            heartbeatTask.cancel(false);
            heartbeatTask = null;
        }
    }

    // ==================== 工具方法 ====================

    private void sendMessage(String message) {
        if (wsSession != null && wsSession.isOpen()) {
            try {
                wsSession.getBasicRemote().sendText(message);
            } catch (IOException e) {
                log.error("[QQGateway] 发送消息失败: {}", e.getMessage(), e);
            }
        } else {
            log.warn("[QQGateway] 无法发送消息: WebSocket 未连接");
        }
    }

    private void closeConnection() {
        try {
            if (wsSession != null && wsSession.isOpen()) {
                wsSession.close();
            }
        } catch (IOException e) {
            log.error("[QQGateway] 关闭连接失败: {}", e.getMessage(), e);
        } finally {
            this.connected = false;
        }
    }

    private void scheduleReconnect() {
        int attempts = reconnectAttempts.incrementAndGet();
        // 指数退避：最多 60 秒
        long delaySeconds = Math.min(properties.getReconnectInterval() * attempts, 60);
        log.info("[QQGateway] {}秒后进行第{}次重连", delaySeconds, attempts);
        scheduler.schedule(this::connect, delaySeconds, TimeUnit.SECONDS);
    }

    public boolean isConnected() {
        return connected && wsSession != null && wsSession.isOpen();
    }
}
