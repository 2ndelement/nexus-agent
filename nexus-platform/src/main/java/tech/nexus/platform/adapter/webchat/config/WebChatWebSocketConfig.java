package tech.nexus.platform.adapter.webchat.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;
import org.springframework.web.socket.server.standard.ServletServerContainerFactoryBean;
import tech.nexus.platform.adapter.webchat.handler.WebChatWebSocketHandler;

/**
 * WebChat WebSocket 配置
 * 端点: /ws/webchat
 * 支持跨域，适配 Vue3 前端
 */
@Slf4j
@Configuration
@EnableWebSocket
public class WebChatWebSocketConfig implements WebSocketConfigurer {

    private final WebChatWebSocketHandler webChatWebSocketHandler;

    @Value("${nexus.platform.webchat.websocket-path:/ws/webchat}")
    private String websocketPath;

    @Value("${nexus.platform.webchat.allowed-origins:*}")
    private String allowedOrigins;

    public WebChatWebSocketConfig(WebChatWebSocketHandler webChatWebSocketHandler) {
        this.webChatWebSocketHandler = webChatWebSocketHandler;
    }

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(webChatWebSocketHandler, websocketPath)
                .setAllowedOrigins(allowedOrigins);
        log.info("[WebChat] WebSocket 端点已注册: path={}, allowedOrigins={}", websocketPath, allowedOrigins);
    }

    /**
     * 配置 WebSocket 容器参数
     */
    @Bean
    public ServletServerContainerFactoryBean createWebSocketContainer() {
        ServletServerContainerFactoryBean container = new ServletServerContainerFactoryBean();
        container.setMaxTextMessageBufferSize(65536);
        container.setMaxBinaryMessageBufferSize(65536);
        container.setMaxSessionIdleTimeout(300000L); // 5分钟无消息断开
        return container;
    }
}
