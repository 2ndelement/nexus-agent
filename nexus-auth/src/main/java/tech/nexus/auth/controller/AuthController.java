package tech.nexus.auth.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import tech.nexus.auth.dto.LoginRequest;
import tech.nexus.auth.dto.RefreshRequest;
import tech.nexus.auth.dto.RegisterRequest;
import tech.nexus.auth.dto.TokenResponse;
import tech.nexus.auth.dto.UserInfoResponse;
import tech.nexus.auth.service.AuthService;
import tech.nexus.common.constant.NexusConstants;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.Result;
import tech.nexus.common.result.ResultCode;

/**
 * 认证接口控制器。
 */
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    /**
     * POST /api/auth/register
     */
    @PostMapping("/register")
    public Result<TokenResponse> register(@Valid @RequestBody RegisterRequest request) {
        return Result.success(authService.register(request));
    }

    /**
     * POST /api/auth/login
     */
    @PostMapping("/login")
    public Result<TokenResponse> login(@Valid @RequestBody LoginRequest request) {
        return Result.success(authService.login(request));
    }

    /**
     * POST /api/auth/refresh
     */
    @PostMapping("/refresh")
    public Result<TokenResponse> refresh(@Valid @RequestBody RefreshRequest request) {
        return Result.success(authService.refresh(request.getRefreshToken()));
    }

    /**
     * POST /api/auth/logout
     * Header: Authorization: Bearer <token>
     */
    @PostMapping("/logout")
    public Result<Void> logout(
            @RequestHeader(value = NexusConstants.HEADER_AUTHORIZATION, required = false)
            String authHeader) {
        String token = extractToken(authHeader);
        authService.logout(token);
        return Result.success();
    }

    /**
     * GET /api/auth/me
     * Header: Authorization: Bearer <token>
     */
    @GetMapping("/me")
    public Result<UserInfoResponse> me(
            @RequestHeader(value = NexusConstants.HEADER_AUTHORIZATION, required = false)
            String authHeader) {
        String token = extractToken(authHeader);
        return Result.success(authService.me(token));
    }

    // ── 私有辅助 ──────────────────────────────────────────────

    /**
     * 从 Authorization 头提取 Bearer Token。
     */
    private String extractToken(String authHeader) {
        if (authHeader == null || !authHeader.startsWith(NexusConstants.BEARER_PREFIX)) {
            throw new BizException(ResultCode.UNAUTHORIZED, "缺少认证 Token");
        }
        return authHeader.substring(NexusConstants.BEARER_PREFIX.length()).trim();
    }
}
