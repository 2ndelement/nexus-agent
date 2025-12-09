package tech.nexus.platform.adapter.qq;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import tech.nexus.platform.adapter.qq.config.QQBotProperties;
import tech.nexus.platform.adapter.qq.service.QQTokenService;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

/**
 * QQTokenService 单元测试（Mock HTTP 客户端，不真实调用 API）
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class QQTokenServiceTest {

    @Mock
    private QQBotProperties properties;

    private QQTokenService tokenService;

    @BeforeEach
    void setUp() {
        when(properties.getTokenRefreshAdvance()).thenReturn(300);
        when(properties.getAppId()).thenReturn("test-app-id");
        when(properties.getAppSecret()).thenReturn("test-secret");
        when(properties.getTokenUrl()).thenReturn("https://bots.qq.com/app/getAppAccessToken");

        tokenService = new QQTokenService(
                properties,
                new com.fasterxml.jackson.databind.ObjectMapper()
        );
    }

    @Test
    void testTokenInvalidWhenNotSet() {
        assertThat(tokenService.isTokenValid()).isFalse();
    }

    @Test
    void testGetAuthorizationHeaderFormat() throws Exception {
        setTokenDirectly("test-access-token-12345", Instant.now().plusSeconds(7200));

        String authHeader = tokenService.getAuthorizationHeader();
        assertThat(authHeader).startsWith("QQBot ");
        assertThat(authHeader).contains("test-access-token-12345");
    }

    @Test
    void testTokenValidWhenNotExpired() throws Exception {
        setTokenDirectly("valid-token", Instant.now().plusSeconds(7200));
        assertThat(tokenService.isTokenValid()).isTrue();
    }

    @Test
    void testTokenInvalidWhenAboutToExpire() throws Exception {
        // Token 将在100秒后过期，但提前300秒刷新，所以应该视为无效
        setTokenDirectly("expiring-token", Instant.now().plusSeconds(100));
        assertThat(tokenService.isTokenValid()).isFalse();
    }

    @Test
    void testTokenExpireTimeIsReturnable() throws Exception {
        Instant expireTime = Instant.now().plusSeconds(7200);
        setTokenDirectly("test-token", expireTime);
        assertThat(tokenService.getTokenExpireTime()).isEqualTo(expireTime);
    }

    // ==================== 工具方法 ====================

    private void setTokenDirectly(String token, Instant expireTime) throws Exception {
        var tokenField = QQTokenService.class.getDeclaredField("currentToken");
        tokenField.setAccessible(true);
        tokenField.set(tokenService, token);

        var expireField = QQTokenService.class.getDeclaredField("tokenExpireTime");
        expireField.setAccessible(true);
        expireField.set(tokenService, expireTime);
    }
}
