package tech.nexus.auth.service;

import io.jsonwebtoken.Claims;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.test.context.ActiveProfiles;
import tech.nexus.auth.dto.LoginRequest;
import tech.nexus.auth.dto.RegisterRequest;
import tech.nexus.auth.dto.TokenResponse;
import tech.nexus.auth.dto.UserInfoResponse;
import tech.nexus.auth.mapper.UserMapper;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.ResultCode;
import tech.nexus.common.utils.JwtUtils;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * AuthService 服务层测试。
 * 使用 H2 内存数据库（@ActiveProfiles("test")），Redis 通过 @MockBean 隔离。
 *
 * <p>V5 重构：移除 tenantId，用户独立注册/登录。
 */
@SpringBootTest
@ActiveProfiles("test")
@DisplayName("AuthService 服务层测试")
class AuthServiceTest {

    @Autowired
    private AuthService authService;

    @Autowired
    private JwtUtils jwtUtils;

    @Autowired
    private UserMapper userMapper;

    @MockBean
    private StringRedisTemplate redisTemplate;

    @SuppressWarnings("unchecked")
    private ValueOperations<String, String> valueOperations =
            (ValueOperations<String, String>) mock(ValueOperations.class);

    @BeforeEach
    void setUp() {
        // Mock Redis 操作
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        doNothing().when(valueOperations).set(anyString(), anyString(), anyLong(), any());
        when(valueOperations.get(anyString())).thenReturn(null);
        when(redisTemplate.hasKey(anyString())).thenReturn(false);
        when(redisTemplate.delete(anyString())).thenReturn(true);

        // 清空测试数据
        userMapper.delete(null);
    }

    // ── 注册 ─────────────────────────────────────────────────

    @Test
    @DisplayName("正常注册 → 返回包含 accessToken 和 refreshToken 的 TokenResponse")
    void register_success_returns_token() {
        RegisterRequest req = buildRegisterReq("alice", "password123", "alice@example.com");

        TokenResponse resp = authService.register(req);

        assertThat(resp.getAccessToken()).isNotBlank();
        assertThat(resp.getRefreshToken()).isNotBlank();
        assertThat(resp.getTokenType()).isEqualTo("Bearer");
        assertThat(resp.getExpiresIn()).isPositive();
    }

    @Test
    @DisplayName("注册后 Token 可解析出正确 userId")
    void register_token_contains_correct_claims() {
        RegisterRequest req = buildRegisterReq("bob", "pass1234", null);

        TokenResponse resp = authService.register(req);

        Claims claims = jwtUtils.parseToken(resp.getAccessToken());
        assertThat(claims.get(JwtUtils.CLAIM_USER_ID, String.class)).isNotNull();
    }

    @Test
    @DisplayName("重复注册同 username → 抛出 BizException(PARAM_ERROR)")
    void register_duplicate_throws_exception() {
        authService.register(buildRegisterReq("charlie", "pass1234", null));

        assertThatThrownBy(() ->
                authService.register(buildRegisterReq("charlie", "different123", null)))
                .isInstanceOf(BizException.class)
                .satisfies(e -> assertThat(((BizException) e).getCode())
                        .isEqualTo(ResultCode.PARAM_ERROR.getCode()));
    }

    // ── 登录 ─────────────────────────────────────────────────

    @Test
    @DisplayName("正常登录 → Token 可解析出正确 userId")
    void login_success_token_has_correct_claims() {
        authService.register(buildRegisterReq("eve", "mySecret99", null));

        LoginRequest login = buildLoginReq("eve", "mySecret99");
        TokenResponse resp = authService.login(login);

        assertThat(resp.getAccessToken()).isNotBlank();
        Claims claims = jwtUtils.parseToken(resp.getAccessToken());
        assertThat(claims.get(JwtUtils.CLAIM_USER_ID, String.class)).isNotNull();
    }

    @Test
    @DisplayName("错误密码登录 → 抛出 BizException(UNAUTHORIZED)，消息为'用户名或密码错误'")
    void login_wrong_password_throws_unauthorized() {
        authService.register(buildRegisterReq("frank", "rightPassword", null));

        assertThatThrownBy(() -> authService.login(buildLoginReq("frank", "wrongPassword")))
                .isInstanceOf(BizException.class)
                .satisfies(e -> {
                    BizException biz = (BizException) e;
                    assertThat(biz.getCode()).isEqualTo(ResultCode.UNAUTHORIZED.getCode());
                    assertThat(biz.getMessage()).isEqualTo("用户名或密码错误");
                });
    }

    @Test
    @DisplayName("不存在的用户登录 → 统一返回'用户名或密码错误'（不暴露用户不存在）")
    void login_nonexistent_user_throws_same_error() {
        assertThatThrownBy(() -> authService.login(buildLoginReq("ghost_xyz", "any")))
                .isInstanceOf(BizException.class)
                .satisfies(e -> {
                    BizException biz = (BizException) e;
                    assertThat(biz.getCode()).isEqualTo(ResultCode.UNAUTHORIZED.getCode());
                    assertThat(biz.getMessage()).isEqualTo("用户名或密码错误");
                });
    }

    // ── Refresh Token ──────────────────────────────────────────

    @Test
    @DisplayName("用有效 Refresh Token 刷新 → 返回新 Access Token")
    void refresh_with_valid_token_returns_new_access_token() {
        TokenResponse regResp = authService.register(buildRegisterReq("grace", "pass1234", null));
        String refreshToken = regResp.getRefreshToken();

        // Mock Redis 返回存储的 refresh token
        when(valueOperations.get(argThat((String k) -> k != null && k.contains(":refresh:"))))
                .thenReturn(refreshToken);

        TokenResponse newResp = authService.refresh(refreshToken);

        assertThat(newResp.getAccessToken()).isNotBlank();
        assertThat(newResp.getAccessToken()).isNotEqualTo(regResp.getAccessToken());
    }

    @Test
    @DisplayName("用无效 Refresh Token 刷新 → 抛出 BizException(TOKEN_INVALID)")
    void refresh_with_invalid_token_throws_exception() {
        assertThatThrownBy(() -> authService.refresh("not.a.valid.jwt.token"))
                .isInstanceOf(BizException.class)
                .satisfies(e -> assertThat(((BizException) e).getCode())
                        .isEqualTo(ResultCode.TOKEN_INVALID.getCode()));
    }

    @Test
    @DisplayName("Redis 中 Refresh Token 不一致 → 抛出 BizException(TOKEN_INVALID)")
    void refresh_with_mismatched_redis_token_throws_exception() {
        TokenResponse regResp = authService.register(buildRegisterReq("henry", "pass5678", null));

        // Redis 返回不同的 token（模拟 token 已被替换）
        when(valueOperations.get(argThat((String k) -> k != null && k.contains(":refresh:"))))
                .thenReturn("different.token.here");

        assertThatThrownBy(() -> authService.refresh(regResp.getRefreshToken()))
                .isInstanceOf(BizException.class)
                .satisfies(e -> assertThat(((BizException) e).getCode())
                        .isEqualTo(ResultCode.TOKEN_INVALID.getCode()));
    }

    // ── Logout + 黑名单 ────────────────────────────────────────

    @Test
    @DisplayName("Logout 后 Token 进入黑名单 → 再次访问 /me 返回 UNAUTHORIZED")
    void logout_then_me_returns_unauthorized() {
        TokenResponse regResp = authService.register(buildRegisterReq("iris", "pass9999", null));
        String accessToken = regResp.getAccessToken();

        // 解析 jti
        Claims claims = jwtUtils.parseToken(accessToken);
        String jti = claims.getId();

        // 调用 logout
        authService.logout(accessToken);

        // 验证黑名单 key 被写入 Redis
        verify(valueOperations, atLeastOnce())
                .set(eq("nexus:blacklist:" + jti), eq("1"), anyLong(), any());

        // 模拟 Redis 黑名单命中（logout 后再次访问）
        when(redisTemplate.hasKey("nexus:blacklist:" + jti)).thenReturn(true);

        assertThatThrownBy(() -> authService.me(accessToken))
                .isInstanceOf(BizException.class)
                .satisfies(e -> assertThat(((BizException) e).getCode())
                        .isEqualTo(ResultCode.UNAUTHORIZED.getCode()));
    }

    // ── /me ───────────────────────────────────────────────────

    @Test
    @DisplayName("用有效 Access Token 访问 /me → 返回正确用户信息")
    void me_with_valid_token_returns_user_info() {
        authService.register(buildRegisterReq("jack", "pass0000", "jack@example.com"));

        // 重新登录获取 access token
        LoginRequest login = buildLoginReq("jack", "pass0000");
        TokenResponse resp = authService.login(login);

        UserInfoResponse info = authService.me(resp.getAccessToken());

        assertThat(info.getUsername()).isEqualTo("jack");
        assertThat(info.getEmail()).isEqualTo("jack@example.com");
        assertThat(info.getRoles()).contains("USER");
    }

    // ── 辅助方法 ──────────────────────────────────────────────

    private RegisterRequest buildRegisterReq(String username,
                                              String password, String email) {
        RegisterRequest req = new RegisterRequest();
        req.setUsername(username);
        req.setPassword(password);
        req.setEmail(email);
        return req;
    }

    private LoginRequest buildLoginReq(String username, String password) {
        LoginRequest req = new LoginRequest();
        req.setUsername(username);
        req.setPassword(password);
        return req;
    }
}
