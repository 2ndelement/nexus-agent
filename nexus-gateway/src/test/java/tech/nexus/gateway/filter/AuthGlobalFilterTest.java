package tech.nexus.gateway.filter;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.impl.DefaultClaims;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.http.HttpHeaders;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;
import tech.nexus.common.constant.NexusConstants;
import tech.nexus.common.utils.JwtUtils;
import tech.nexus.gateway.config.WhiteListConfig;

import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

/**
 * AuthGlobalFilter 测试：
 * 1. 白名单路径放行
 * 2. 缺少 Token 拒绝
 * 3. 有效 Token 放行
 * 4. 已登出 Token（黑名单）拒绝
 */
@ExtendWith(MockitoExtension.class)
class AuthGlobalFilterTest {

    @Mock
    private JwtUtils jwtUtils;

    @Mock
    private WhiteListConfig whiteListConfig;

    @Mock
    private StringRedisTemplate redisTemplate;

    @Mock
    private ValueOperations<String, String> valueOps;

    @Mock
    private GatewayFilterChain chain;

    @InjectMocks
    private AuthGlobalFilter filter;

    @BeforeEach
    void setUp() {
        lenient().when(redisTemplate.opsForValue()).thenReturn(valueOps);
    }

    @Test
    void whitelist_path_should_pass() {
        MockServerHttpRequest request = MockServerHttpRequest.get("/api/auth/login").build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);
        when(whiteListConfig.isWhiteListed("/api/auth/login")).thenReturn(true);
        when(chain.filter(any())).thenReturn(Mono.empty());

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        verify(chain).filter(any());
    }

    @Test
    void missing_token_should_return_401() {
        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tenant/list").build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);
        when(whiteListConfig.isWhiteListed(anyString())).thenReturn(false);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        // 没有调用 chain.filter → 被拦截
        verify(chain, never()).filter(any());
    }

    @Test
    void valid_token_should_pass_and_inject_headers() {
        MockServerHttpRequest request = MockServerHttpRequest.get("/api/session/list")
                .header(NexusConstants.HEADER_AUTHORIZATION, NexusConstants.BEARER_PREFIX + "valid-token")
                .build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);
        when(whiteListConfig.isWhiteListed(anyString())).thenReturn(false);

        DefaultClaims claims = new DefaultClaims();
        claims.put(JwtUtils.CLAIM_USER_ID, "user-1");
        claims.put(JwtUtils.CLAIM_TENANT_ID, "tenant-1");
        claims.put(JwtUtils.CLAIM_ROLES, List.of("ADMIN"));
        claims.setId("jti-001");

        when(jwtUtils.parseToken("valid-token")).thenReturn(claims);
        when(valueOps.get("nexus:blacklist:jti-001")).thenReturn(null);
        when(chain.filter(any())).thenReturn(Mono.empty());

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        verify(chain).filter(any());
    }

    @Test
    void blacklisted_token_should_return_401() {
        MockServerHttpRequest request = MockServerHttpRequest.get("/api/session/list")
                .header(NexusConstants.HEADER_AUTHORIZATION, NexusConstants.BEARER_PREFIX + "logged-out-token")
                .build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);
        when(whiteListConfig.isWhiteListed(anyString())).thenReturn(false);

        DefaultClaims claims = new DefaultClaims();
        claims.put(JwtUtils.CLAIM_USER_ID, "user-1");
        claims.put(JwtUtils.CLAIM_TENANT_ID, "tenant-1");
        claims.setId("jti-blacklisted");

        when(jwtUtils.parseToken("logged-out-token")).thenReturn(claims);
        // 该 jti 在黑名单中
        when(valueOps.get("nexus:blacklist:jti-blacklisted")).thenReturn("1");

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        // 被黑名单拦截，不应调用 chain.filter
        verify(chain, never()).filter(any());
    }
}
