package tech.nexus.platform.adapter.qq.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import tech.nexus.platform.adapter.qq.config.QQBotProperties;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.locks.ReentrantLock;

/**
 * QQ Bot AccessToken 管理服务
 * <p>
 * - 自动获取/刷新 AccessToken（有效期7200秒）
 * - 提前 tokenRefreshAdvance 秒刷新（默认300秒）
 * - 线程安全
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class QQTokenService {

    private final QQBotProperties properties;
    private final ObjectMapper objectMapper;

    private volatile String currentToken;
    private volatile Instant tokenExpireTime = Instant.EPOCH;
    private final ReentrantLock lock = new ReentrantLock();

    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    /**
     * 获取有效的 AccessToken
     * 如果 Token 即将过期（< tokenRefreshAdvance 秒），则自动刷新
     */
    public String getAccessToken() {
        if (isTokenValid()) {
            return currentToken;
        }
        return refreshToken();
    }

    /**
     * 获取 Authorization Header 值（格式: "QQBot {token}"）
     */
    public String getAuthorizationHeader() {
        return "QQBot " + getAccessToken();
    }

    /**
     * 定时刷新 Token（每小时检查一次）
     */
    @Scheduled(fixedDelay = 3600000)
    public void scheduledRefresh() {
        if (properties.isEnabled() && !isTokenValid()) {
            log.info("[QQToken] 定时刷新 AccessToken");
            refreshToken();
        }
    }

    /**
     * 判断 Token 是否仍然有效（剩余时间 > tokenRefreshAdvance）
     */
    public boolean isTokenValid() {
        return currentToken != null
                && Instant.now().plusSeconds(properties.getTokenRefreshAdvance()).isBefore(tokenExpireTime);
    }

    /**
     * 刷新 AccessToken
     */
    public String refreshToken() {
        lock.lock();
        try {
            // double-check
            if (isTokenValid()) {
                return currentToken;
            }

            log.info("[QQToken] 开始获取 AccessToken, appId={}", properties.getAppId());

            Map<String, String> body = Map.of(
                    "appId", properties.getAppId(),
                    "clientSecret", properties.getAppSecret()
            );
            String requestBody = objectMapper.writeValueAsString(body);

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(properties.getTokenUrl()))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                    .timeout(Duration.ofSeconds(15))
                    .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() != 200) {
                log.error("[QQToken] 获取 AccessToken 失败: status={}, body={}", response.statusCode(), response.body());
                throw new RuntimeException("获取 QQ AccessToken 失败: HTTP " + response.statusCode());
            }

            JsonNode respNode = objectMapper.readTree(response.body());
            String newToken = respNode.path("access_token").asText();
            int expiresIn = respNode.path("expires_in").asInt(7200);

            if (newToken.isBlank()) {
                log.error("[QQToken] 响应中无 access_token: {}", response.body());
                throw new RuntimeException("QQ AccessToken 响应异常: " + response.body());
            }

            currentToken = newToken;
            tokenExpireTime = Instant.now().plusSeconds(expiresIn);
            log.info("[QQToken] AccessToken 刷新成功, expiresIn={}s, expireAt={}", expiresIn, tokenExpireTime);

            return currentToken;
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            log.error("[QQToken] 刷新 AccessToken 异常: {}", e.getMessage(), e);
            throw new RuntimeException("刷新 QQ AccessToken 失败", e);
        } finally {
            lock.unlock();
        }
    }

    /**
     * 获取 Token 过期时间（测试用）
     */
    public Instant getTokenExpireTime() {
        return tokenExpireTime;
    }
}
