package tech.nexus.auth.service;

import tech.nexus.auth.dto.LoginRequest;
import tech.nexus.auth.dto.RegisterRequest;
import tech.nexus.auth.dto.TokenResponse;
import tech.nexus.auth.dto.UserInfoResponse;

/**
 * 认证服务接口。
 */
public interface AuthService {

    /**
     * 用户注册。
     *
     * @param request 注册请求
     * @return 注册成功后的 Token 响应
     */
    TokenResponse register(RegisterRequest request);

    /**
     * 用户登录。
     * 登录失败时统一抛出 BizException(UNAUTHORIZED, "用户名或密码错误")，
     * 不区分"用户不存在"与"密码错误"。
     *
     * @param request 登录请求
     * @return Token 响应
     */
    TokenResponse login(LoginRequest request);

    /**
     * 刷新 Access Token。
     *
     * @param refreshToken Refresh Token 字符串
     * @return 新 Token 响应
     */
    TokenResponse refresh(String refreshToken);

    /**
     * 登出：将 Access Token 的 jti 写入 Redis 黑名单。
     *
     * @param accessToken 当前 Access Token（不含 "Bearer " 前缀）
     */
    void logout(String accessToken);

    /**
     * 获取当前用户信息（通过 Access Token 解析）。
     *
     * @param accessToken 当前 Access Token（不含 "Bearer " 前缀）
     * @return 用户信息
     */
    UserInfoResponse me(String accessToken);
}
