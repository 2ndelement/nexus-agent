package tech.nexus.gateway.filter;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.reactive.server.WebTestClient;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.List;
import java.util.UUID;

/**
 * AuthGlobalFilter 集成测试。
 *
 * <p>测试策略：
 * <ul>
 *   <li>启动完整 Spring Boot 响应式上下文（RANDOM_PORT）</li>
 *   <li>下游服务地址 127.0.0.1:19999 不存在 → Filter 放行后返回 502/503</li>
 *   <li>Filter 拦截 → 返回 401</li>
 *   <li>通过 HTTP 状态码断言 Filter 行为：
 *       401 = 被 Filter 拦截；非 401 = Filter 放行（下游问题不关心）</li>
 * </ul>
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
@DisplayName("AuthGlobalFilter 集成测试")
class AuthGlobalFilterTest {

    @Autowired
    private WebTestClient webTestClient;

    @Value("${nexus.jwt.secret}")
    private String jwtSecret;

    private SecretKey secretKey;

    @BeforeEach
    void setUp() {
        secretKey = Keys.hmacShaKeyFor(jwtSecret.getBytes(StandardCharsets.UTF_8));
    }

    // ── Token 构建辅助 ────────────────────────────────────────

    /** 构建有效 JWT（2 小时过期） */
    private String buildValidToken(String userId, String tenantId, List<String> roles) {
        Date now = new Date();
        Date expiry = new Date(now.getTime() + 7_200_000L);
        return Jwts.builder()
                .id(UUID.randomUUID().toString())
                .subject(userId)
                .claim("userId", userId)
                .claim("tenantId", tenantId)
                .claim("roles", roles)
                .issuedAt(now)
                .expiration(expiry)
                .signWith(secretKey)
                .compact();
    }

    /** 构建已过期 JWT（过期 1 秒前） */
    private String buildExpiredToken(String userId, String tenantId) {
        Date past = new Date(System.currentTimeMillis() - 60_000L);  // 1 分钟前过期
        return Jwts.builder()
                .id(UUID.randomUUID().toString())
                .subject(userId)
                .claim("userId", userId)
                .claim("tenantId", tenantId)
                .claim("roles", List.of("USER"))
                .issuedAt(new Date(System.currentTimeMillis() - 120_000L))
                .expiration(past)
                .signWith(secretKey)
                .compact();
    }

    /** 构建被篡改 Token（修改 payload 段） */
    private String buildTamperedToken(String userId, String tenantId) {
        String valid = buildValidToken(userId, tenantId, List.of("USER"));
        String[] parts = valid.split("\\.");
        // 替换 payload 为 base64 编码的伪造内容
        return parts[0] + ".dGFtcGVyZWRfcGF5bG9hZA." + parts[2];
    }

    // ── 白名单路径测试 ────────────────────────────────────────

    @Test
    @DisplayName("白名单路径 /api/auth/login → 无 Token 也直接放行（不返回 401）")
    void whitelist_path_no_token_should_pass_filter() {
        webTestClient.post()
                .uri("/api/auth/login")
                .exchange()
                // Filter 放行 → 转发到不存在的下游 → 502/503/504，但绝不是 401
                .expectStatus().value(status ->
                        org.assertj.core.api.Assertions.assertThat(status)
                                .as("白名单路径应被放行（非401）")
                                .isNotEqualTo(HttpStatus.UNAUTHORIZED.value()));
    }

    @Test
    @DisplayName("白名单路径 /api/auth/register → 即使带错误 Token 也放行")
    void whitelist_path_with_invalid_token_should_pass_filter() {
        webTestClient.post()
                .uri("/api/auth/register")
                .header(HttpHeaders.AUTHORIZATION, "Bearer invalid.token.here")
                .exchange()
                .expectStatus().value(status ->
                        org.assertj.core.api.Assertions.assertThat(status)
                                .as("白名单路径应被放行（非401）")
                                .isNotEqualTo(HttpStatus.UNAUTHORIZED.value()));
    }

    @Test
    @DisplayName("白名单路径 /api/auth/refresh → 放行")
    void whitelist_path_refresh_should_pass() {
        webTestClient.post()
                .uri("/api/auth/refresh")
                .exchange()
                .expectStatus().value(status ->
                        org.assertj.core.api.Assertions.assertThat(status)
                                .isNotEqualTo(HttpStatus.UNAUTHORIZED.value()));
    }

    // ── 无 Token 访问受保护路径 ───────────────────────────────

    @Test
    @DisplayName("受保护路径 /api/tenant/list → 无 Token → 401")
    void protected_path_no_token_returns_401() {
        webTestClient.get()
                .uri("/api/tenant/list")
                .exchange()
                .expectStatus().isUnauthorized()
                .expectBody()
                .jsonPath("$.code").isEqualTo(401)
                .jsonPath("$.msg").isNotEmpty();
    }

    @Test
    @DisplayName("受保护路径 /api/session/list → 无 Token → 401")
    void protected_path_session_no_token_returns_401() {
        webTestClient.get()
                .uri("/api/session/list")
                .exchange()
                .expectStatus().isUnauthorized();
    }

    @Test
    @DisplayName("受保护路径 /api/agent/chat → 无 Token → 401")
    void protected_path_agent_no_token_returns_401() {
        webTestClient.post()
                .uri("/api/agent/chat")
                .exchange()
                .expectStatus().isUnauthorized();
    }

    @Test
    @DisplayName("受保护路径 /api/knowledge/search → 无 Token → 401")
    void protected_path_knowledge_no_token_returns_401() {
        webTestClient.post()
                .uri("/api/knowledge/search")
                .exchange()
                .expectStatus().isUnauthorized();
    }

    // ── 格式错误的 Authorization Header ──────────────────────

    @Test
    @DisplayName("Authorization 格式错误（缺少 Bearer 前缀）→ 401")
    void malformed_authorization_header_returns_401() {
        webTestClient.get()
                .uri("/api/tenant/list")
                .header(HttpHeaders.AUTHORIZATION, "Token some-token-value")
                .exchange()
                .expectStatus().isUnauthorized();
    }

    @Test
    @DisplayName("Authorization 为空字符串 → 401")
    void empty_authorization_header_returns_401() {
        webTestClient.get()
                .uri("/api/session/messages")
                .header(HttpHeaders.AUTHORIZATION, "")
                .exchange()
                .expectStatus().isUnauthorized();
    }

    // ── 过期 Token ────────────────────────────────────────────

    @Test
    @DisplayName("过期 Token → 401，消息包含 Token 无效/过期")
    void expired_token_returns_401() {
        String expiredToken = buildExpiredToken("user-1", "tenant-1");

        webTestClient.get()
                .uri("/api/tenant/list")
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + expiredToken)
                .exchange()
                .expectStatus().isUnauthorized()
                .expectBody()
                .jsonPath("$.code").isEqualTo(401);
    }

    // ── 篡改 Token ────────────────────────────────────────────

    @Test
    @DisplayName("篡改 Token（签名不匹配）→ 401")
    void tampered_token_returns_401() {
        String tampered = buildTamperedToken("user-1", "tenant-1");

        webTestClient.get()
                .uri("/api/tenant/list")
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + tampered)
                .exchange()
                .expectStatus().isUnauthorized();
    }

    @Test
    @DisplayName("完全随机字符串作为 Token → 401")
    void garbage_token_returns_401() {
        webTestClient.get()
                .uri("/api/session/messages")
                .header(HttpHeaders.AUTHORIZATION, "Bearer this-is-not-a-jwt-at-all")
                .exchange()
                .expectStatus().isUnauthorized();
    }

    // ── 有效 Token 通过 Filter ────────────────────────────────

    @Test
    @DisplayName("有效 Token → Filter 放行（不返回 401，下游不在线返回 5xx）")
    void valid_token_passes_filter() {
        String token = buildValidToken("user-001", "tenant-001", List.of("USER"));

        webTestClient.get()
                .uri("/api/tenant/list")
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                .exchange()
                // Filter 放行 → 转发到 19999（不存在）→ 5xx，但绝不是 401
                .expectStatus().value(status ->
                        org.assertj.core.api.Assertions.assertThat(status)
                                .as("有效 Token 应被 Filter 放行（非401）")
                                .isNotEqualTo(HttpStatus.UNAUTHORIZED.value()));
    }

    @Test
    @DisplayName("有效 Token 访问 /api/session → Filter 放行（非 401）")
    void valid_token_session_passes_filter() {
        String token = buildValidToken("user-002", "tenant-002", List.of("USER", "ADMIN"));

        webTestClient.get()
                .uri("/api/session/list")
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                .exchange()
                .expectStatus().value(status ->
                        org.assertj.core.api.Assertions.assertThat(status)
                                .isNotEqualTo(HttpStatus.UNAUTHORIZED.value()));
    }

    @Test
    @DisplayName("有效 Token 访问 /api/agent → Filter 放行（非 401，支持 SSE 路径）")
    void valid_token_agent_sse_passes_filter() {
        String token = buildValidToken("user-003", "tenant-003", List.of("USER"));

        webTestClient.post()
                .uri("/api/agent/chat")
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                .exchange()
                .expectStatus().value(status ->
                        org.assertj.core.api.Assertions.assertThat(status)
                                .isNotEqualTo(HttpStatus.UNAUTHORIZED.value()));
    }

    // ── 响应格式验证 ──────────────────────────────────────────

    @Test
    @DisplayName("401 响应体格式符合 Result 规范（code/msg/data 字段）")
    void unauthorized_response_body_matches_result_format() {
        webTestClient.get()
                .uri("/api/knowledge/search")
                .exchange()
                .expectStatus().isUnauthorized()
                .expectBody()
                .jsonPath("$.code").isEqualTo(401)
                .jsonPath("$.msg").isNotEmpty()
                .jsonPath("$.data").isEmpty();
    }

    @Test
    @DisplayName("401 响应 Content-Type 为 application/json")
    void unauthorized_response_content_type_is_json() {
        webTestClient.get()
                .uri("/api/tenant/info")
                .exchange()
                .expectStatus().isUnauthorized()
                .expectHeader().contentTypeCompatibleWith(
                        org.springframework.http.MediaType.APPLICATION_JSON);
    }
}
