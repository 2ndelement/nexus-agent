package tech.nexus.auth.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import tech.nexus.auth.dto.LoginRequest;
import tech.nexus.auth.dto.RefreshRequest;
import tech.nexus.auth.dto.RegisterRequest;
import tech.nexus.auth.dto.TokenResponse;
import tech.nexus.auth.dto.UserInfoResponse;
import tech.nexus.auth.service.AuthService;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.ResultCode;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * AuthController 控制器层测试。
 * 使用完整 Spring Boot 上下文（H2 + MockMvc），AuthService / Redis 全部 Mock。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DisplayName("AuthController 控制器层测试")
class AuthControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private AuthService authService;

    @MockBean
    private StringRedisTemplate redisTemplate;

    private static final String BASE_URL = "/api/auth";

    private TokenResponse mockToken() {
        return TokenResponse.builder()
                .accessToken("mock.access.token")
                .refreshToken("mock.refresh.token")
                .expiresIn(7200L)
                .tokenType("Bearer")
                .build();
    }

    // ── POST /register ────────────────────────────────────────

    @Test
    @DisplayName("POST /register 正常注册 → 200 + token")
    void register_success() throws Exception {
        when(authService.register(any())).thenReturn(mockToken());

        RegisterRequest req = new RegisterRequest();
        req.setUsername("alice");
        req.setPassword("password123");
        req.setEmail("alice@example.com");

        mockMvc.perform(post(BASE_URL + "/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.accessToken").value("mock.access.token"))
                .andExpect(jsonPath("$.data.tokenType").value("Bearer"));
    }

    @Test
    @DisplayName("POST /register 重复注册 → 400 错误")
    void register_duplicate_returns_400() throws Exception {
        when(authService.register(any()))
                .thenThrow(new BizException(ResultCode.PARAM_ERROR, "用户名已存在"));

        RegisterRequest req = new RegisterRequest();
        req.setUsername("bob");
        req.setPassword("password123");

        mockMvc.perform(post(BASE_URL + "/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(400))
                .andExpect(jsonPath("$.msg").value("用户名已存在"));
    }

    @Test
    @DisplayName("POST /register 缺少必填字段 → 400 参数校验错误")
    void register_missing_fields_returns_400() throws Exception {
        // username 和 password 缺失
        String json = "{}";

        mockMvc.perform(post(BASE_URL + "/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(400));
    }

    // ── POST /login ────────────────────────────────────────────

    @Test
    @DisplayName("POST /login 正常登录 → 200 + token")
    void login_success() throws Exception {
        when(authService.login(any())).thenReturn(mockToken());

        LoginRequest req = new LoginRequest();
        req.setUsername("alice");
        req.setPassword("password123");

        mockMvc.perform(post(BASE_URL + "/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.accessToken").exists());
    }

    @Test
    @DisplayName("POST /login 错误密码 → 401 + '用户名或密码错误'")
    void login_wrong_password_returns_401() throws Exception {
        when(authService.login(any()))
                .thenThrow(new BizException(ResultCode.UNAUTHORIZED, "用户名或密码错误"));

        LoginRequest req = new LoginRequest();
        req.setUsername("alice");
        req.setPassword("wrongpass");

        mockMvc.perform(post(BASE_URL + "/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(401))
                .andExpect(jsonPath("$.msg").value("用户名或密码错误"));
    }

    // ── POST /refresh ──────────────────────────────────────────

    @Test
    @DisplayName("POST /refresh 有效 refreshToken → 200 + 新 token")
    void refresh_success() throws Exception {
        TokenResponse newToken = TokenResponse.builder()
                .accessToken("new.access.token")
                .refreshToken("new.refresh.token")
                .expiresIn(7200L)
                .tokenType("Bearer")
                .build();
        when(authService.refresh(anyString())).thenReturn(newToken);

        RefreshRequest req = new RefreshRequest();
        req.setRefreshToken("old.refresh.token");

        mockMvc.perform(post(BASE_URL + "/refresh")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.accessToken").value("new.access.token"));
    }

    @Test
    @DisplayName("POST /refresh 无效 token → 3002 TOKEN_INVALID")
    void refresh_invalid_token_returns_3002() throws Exception {
        when(authService.refresh(anyString()))
                .thenThrow(new BizException(ResultCode.TOKEN_INVALID));

        RefreshRequest req = new RefreshRequest();
        req.setRefreshToken("bad.token.value");

        mockMvc.perform(post(BASE_URL + "/refresh")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(3002));
    }

    // ── POST /logout ───────────────────────────────────────────

    @Test
    @DisplayName("POST /logout 正常登出 → 200")
    void logout_success() throws Exception {
        doNothing().when(authService).logout(anyString());

        mockMvc.perform(post(BASE_URL + "/logout")
                        .header("Authorization", "Bearer valid.access.token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));
    }

    @Test
    @DisplayName("POST /logout 无 Authorization header → 401")
    void logout_no_token_returns_401() throws Exception {
        mockMvc.perform(post(BASE_URL + "/logout"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(401));
    }

    // ── GET /me ────────────────────────────────────────────────

    @Test
    @DisplayName("GET /me 有效 token → 200 + 用户信息")
    void me_success() throws Exception {
        UserInfoResponse info = UserInfoResponse.builder()
                .userId(1L)
                .username("alice")
                .email("alice@example.com")
                .roles(List.of("USER"))
                .build();
        when(authService.me(anyString())).thenReturn(info);

        mockMvc.perform(get(BASE_URL + "/me")
                        .header("Authorization", "Bearer valid.token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.username").value("alice"));
    }

    @Test
    @DisplayName("GET /me 注销后 token → 401")
    void me_with_blacklisted_token_returns_401() throws Exception {
        when(authService.me(anyString()))
                .thenThrow(new BizException(ResultCode.UNAUTHORIZED, "Token 已注销"));

        mockMvc.perform(get(BASE_URL + "/me")
                        .header("Authorization", "Bearer blacklisted.token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(401));
    }

    @Test
    @DisplayName("GET /me 无 Authorization header → 401")
    void me_no_token_returns_401() throws Exception {
        mockMvc.perform(get(BASE_URL + "/me"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(401));
    }
}
