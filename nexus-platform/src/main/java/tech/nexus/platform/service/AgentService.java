package tech.nexus.platform.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.client.ServiceInstance;
import org.springframework.cloud.client.discovery.DiscoveryClient;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import reactor.core.scheduler.Schedulers;
import tech.nexus.platform.common.model.PlatformMessage;

import jakarta.annotation.PostConstruct;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Agent 服务 - 封装对 agent-engine 的 HTTP 调用
 * 支持 Nacos 服务发现
 */
@Slf4j
@Service
public class AgentService {

    private final DiscoveryClient discoveryClient;
    private final ObjectMapper objectMapper;
    private WebClient webClient;
    private ExecutorService executorService;

    @Value("${nexus.agent-engine.service-name:nexus-agent-engine}")
    private String serviceName;

    /**
     * 缓存服务 URL，减少频繁查询
     */
    private final AtomicReference<String> cachedServiceUrl = new AtomicReference<>();
    private volatile long lastCacheTime = 0;
    private static final long CACHE_TTL = 60000; // 1分钟缓存

    public AgentService(DiscoveryClient discoveryClient, ObjectMapper objectMapper) {
        this.discoveryClient = discoveryClient;
        this.objectMapper = objectMapper;
    }

    @PostConstruct
    public void init() {
        // 初始化线程池
        this.executorService = Executors.newFixedThreadPool(
                Runtime.getRuntime().availableProcessors() * 2,
                r -> {
                    Thread t = new Thread(r, "agent-http-pool");
                    t.setDaemon(true);
                    return t;
                }
        );
        
        // 初始化 WebClient
        this.webClient = WebClient.builder()
                .clientConnector(new reactor.netty.http.client.HttpClient())
                .build();
    }

    /**
     * 获取 agent-engine 服务地址（带缓存）
     */
    private String getAgentEngineUrl() {
        long now = System.currentTimeMillis();
        
        // 检查缓存
        if (cachedServiceUrl.get() != null && (now - lastCacheTime) < CACHE_TTL) {
            return cachedServiceUrl.get();
        }

        // 重新查询
        List<ServiceInstance> instances = discoveryClient.getInstances(serviceName);
        if (instances.isEmpty()) {
            // 尝试备用服务名
            instances = discoveryClient.getInstances("nexus-agent-engine");
        }
        
        if (instances.isEmpty()) {
            throw new RuntimeException("Service not found: " + serviceName);
        }
        
        // 加权随机选择（简单实现：轮询）
        ServiceInstance instance = instances.get(0);
        String url = instance.getUri().toString();
        
        // 更新缓存
        cachedServiceUrl.set(url);
        lastCacheTime = now;
        
        log.debug("[AgentService] 解析服务地址: {} -> {}", serviceName, url);
        return url;
    }

    /**
     * 流式聊天 - 逐 token 推送到 WebSocket
     * 使用线程池避免阻塞
     */
    public void streamChatToWebSocket(PlatformMessage message, WebSocketSession session) {
        executorService.submit(() -> {
            try {
                String baseUrl = getAgentEngineUrl();
                String url = baseUrl + "/api/v1/agent/chat/stream";

                webClient.post()
                        .uri(url)
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("X-Tenant-Id", message.getTenantId() != null ? message.getTenantId() : "")
                        .header("X-User-Id", message.getSenderId() != null ? message.getSenderId() : "")
                        .header("X-Conv-Id", message.getChatId() != null ? message.getChatId() : "")
                        .bodyValue(Map.of("message", message.getContent()))
                        .retrieve()
                        .bodyToFlux(String.class)
                        .publishOn(Schedulers.boundedElastic())
                        .subscribe(
                                line -> {
                                    if (line.startsWith("data:")) {
                                        String data = line.substring(5).trim();
                                        if ("[DONE]".equals(data)) {
                                            return;
                                        }
                                        try {
                                            JsonNode node = objectMapper.readTree(data);
                                            String content = node.path("content").asText("");
                                            if (!content.isEmpty()) {
                                                String json = objectMapper.writeValueAsString(Map.of(
                                                        "type", "reply",
                                                        "content", content,
                                                        "messageId", message.getMessageId(),
                                                        "timestamp", LocalDateTime.now().toString()
                                                ));
                                                synchronized (session) {
                                                    if (session.isOpen()) {
                                                        session.sendMessage(new TextMessage(json));
                                                    }
                                                }
                                            }
                                        } catch (Exception e) {
                                            log.error("Error parsing SSE data", e);
                                        }
                                    }
                                },
                                error -> {
                                    log.error("SSE stream error", error);
                                    try {
                                        synchronized (session) {
                                            if (session.isOpen()) {
                                                session.sendMessage(new TextMessage(objectMapper.writeValueAsString(Map.of(
                                                        "type", "error",
                                                        "message", "Agent error: " + error.getMessage()
                                                ))));
                                            }
                                        }
                                    } catch (Exception ex) {
                                        log.error("Failed to send error", ex);
                                    }
                                }
                        );
            } catch (Exception e) {
                log.error("Error calling agent engine", e);
                // 清除缓存，强制下次重新查询
                cachedServiceUrl.set(null);
            }
        });
    }
}
