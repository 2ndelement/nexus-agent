package tech.nexus.common.utils;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@DisplayName("JwtUtils 单元测试")
class JwtUtilsTest {

    /**
     * 测试用密钥（≥ 32 字符，满足 HMAC-SHA256 256-bit 要求）。
     * 注意：测试密钥写在测试代码里是允许的，生产代码中禁止硬编码。
     */
    private static final String TEST_SECRET = "nexus-test-secret-key-at-least-32-chars!!";
    private static final long EXPIRATION_MS = 3_600_000L; // 1 小时

    private JwtUtils jwtUtils;

    @BeforeEach
    void setUp() {
        jwtUtils = new JwtUtils(TEST_SECRET, EXPIRATION_MS);
    }

    // ── 生成与解析 ────────────────────────────────────────────

    @Test
    @DisplayName("generateToken 生成的 Token 可以正确解析出 userId 和 tenantId")
    void generate_and_parse_token_correctly() {
        String token = jwtUtils.generateToken("user-001", "tenant-001",
                List.of("ROLE_ADMIN", "ROLE_USER"));

        assertThat(token).isNotBlank();

        Claims claims = jwtUtils.parseToken(token);

        assertThat(claims.get(JwtUtils.CLAIM_USER_ID, String.class))
                .isEqualTo("user-001");
        assertThat(claims.get(JwtUtils.CLAIM_TENANT_ID, String.class))
                .isEqualTo("tenant-001");
    }

    @Test
    @DisplayName("parseToken 应能解析出 roles 列表")
    void parse_token_contains_roles() {
        List<String> roles = List.of("ROLE_ADMIN", "ROLE_USER");
        String token = jwtUtils.generateToken("user-002", "tenant-002", roles);

        Claims claims = jwtUtils.parseToken(token);

        @SuppressWarnings("unchecked")
        List<String> parsedRoles = claims.get(JwtUtils.CLAIM_ROLES, List.class);
        assertThat(parsedRoles).containsExactlyInAnyOrder("ROLE_ADMIN", "ROLE_USER");
    }

    @Test
    @DisplayName("parseToken subject 应等于 userId")
    void parse_token_subject_equals_user_id() {
        String token = jwtUtils.generateToken("user-sub", "t-001", List.of());
        Claims claims = jwtUtils.parseToken(token);
        assertThat(claims.getSubject()).isEqualTo("user-sub");
    }

    // ── 有效性判断 ────────────────────────────────────────────

    @Test
    @DisplayName("有效 Token isExpired 应返回 false")
    void valid_token_is_not_expired() {
        String token = jwtUtils.generateToken("u1", "t1", List.of());
        assertThat(jwtUtils.isExpired(token)).isFalse();
    }

    @Test
    @DisplayName("极短过期时间生成的 Token 应被检测为已过期")
    void expired_token_detected() throws InterruptedException {
        JwtUtils shortLivedJwt = new JwtUtils(TEST_SECRET, 1L); // 1 毫秒
        String token = shortLivedJwt.generateToken("u2", "t2", List.of());

        // 等待过期
        Thread.sleep(50);

        assertThat(shortLivedJwt.isExpired(token)).isTrue();
    }

    @Test
    @DisplayName("过期 Token 调用 parseToken 应抛出 JwtException")
    void expired_token_parse_throws_exception() throws InterruptedException {
        JwtUtils shortLivedJwt = new JwtUtils(TEST_SECRET, 1L);
        String token = shortLivedJwt.generateToken("u3", "t3", List.of());

        Thread.sleep(50);

        assertThatThrownBy(() -> shortLivedJwt.parseToken(token))
                .isInstanceOf(JwtException.class);
    }

    // ── 篡改检测 ──────────────────────────────────────────────

    @Test
    @DisplayName("篡改 Token payload 后 parseToken 应抛出 JwtException")
    void tampered_token_throws_exception() {
        String token = jwtUtils.generateToken("u4", "t4", List.of());

        // 修改 payload 部分（中间 Base64 段）
        String[] parts = token.split("\\.");
        assertThat(parts).hasSize(3);
        String tamperedToken = parts[0] + ".dGFtcGVyZWQ" + "." + parts[2];

        assertThatThrownBy(() -> jwtUtils.parseToken(tamperedToken))
                .isInstanceOf(JwtException.class);
    }

    @Test
    @DisplayName("篡改 Token 后 isExpired 应返回 true（视同无效）")
    void tampered_token_is_considered_expired() {
        String token = jwtUtils.generateToken("u5", "t5", List.of());

        String[] parts = token.split("\\.");
        String tamperedToken = parts[0] + ".dGFtcGVyZWQ" + "." + parts[2];

        assertThat(jwtUtils.isExpired(tamperedToken)).isTrue();
    }

    @Test
    @DisplayName("使用不同密钥签名的 Token 应被拒绝")
    void token_signed_with_different_key_is_rejected() {
        JwtUtils otherJwt = new JwtUtils("completely-different-secret-key-for-test!!", EXPIRATION_MS);
        String token = otherJwt.generateToken("u6", "t6", List.of());

        // 用 jwtUtils（不同密钥）解析，应抛出异常
        assertThatThrownBy(() -> jwtUtils.parseToken(token))
                .isInstanceOf(JwtException.class);
    }

    // ── 构造参数校验 ──────────────────────────────────────────

    @Test
    @DisplayName("secretKey 为 null 时构造应抛出 NullPointerException")
    void constructor_null_secret_throws_npe() {
        assertThatThrownBy(() -> new JwtUtils(null, EXPIRATION_MS))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    @DisplayName("secretKey 为空字符串时构造应抛出 IllegalArgumentException")
    void constructor_blank_secret_throws_iae() {
        assertThatThrownBy(() -> new JwtUtils("   ", EXPIRATION_MS))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
