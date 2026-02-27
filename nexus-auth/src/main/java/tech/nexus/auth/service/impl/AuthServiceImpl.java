package tech.nexus.auth.service.impl;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tech.nexus.auth.dto.LoginRequest;
import tech.nexus.auth.dto.RegisterRequest;
import tech.nexus.auth.dto.TokenResponse;
import tech.nexus.auth.dto.TokenResponse.OrganizationWithRole;
import tech.nexus.auth.dto.TokenResponse.UserInfo;
import tech.nexus.auth.dto.UserInfoResponse;
import tech.nexus.auth.entity.User;
import tech.nexus.auth.mapper.OrganizationUserMapper;
import tech.nexus.auth.mapper.UserMapper;
import tech.nexus.auth.service.AuthService;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.ResultCode;
import tech.nexus.common.utils.JwtUtils;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Date;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * 认证服务实现。
 *
 * <p>V5 重构：移除 tenantId 绑定，用户独立注册/登录。
 *
 * <p>Access Token 内嵌 {@code jti}（UUID），用于登出后加入 Redis 黑名单。
 * Refresh Token 存入 Redis，key = {@code nexus:refresh:{userId}}。
 * 黑名单 key = {@code nexus:blacklist:{jti}}。
 */
@Slf4j
@Service
public class AuthServiceImpl implements AuthService {

    private final UserMapper userMapper;
    private final OrganizationUserMapper organizationUserMapper;
    private final JwtUtils jwtUtils;
    private final StringRedisTemplate redisTemplate;
    private final BCryptPasswordEncoder passwordEncoder;
    private final SecretKey secretKey;

    @Value("${nexus.jwt.access-token-expiration-ms:7200000}")
    private long accessTokenExpirationMs;

    @Value("${nexus.jwt.refresh-token-expiration-ms:2592000000}")
    private long refreshTokenExpirationMs;

    public AuthServiceImpl(
            UserMapper userMapper,
            OrganizationUserMapper organizationUserMapper,
            JwtUtils jwtUtils,
            StringRedisTemplate redisTemplate,
            BCryptPasswordEncoder passwordEncoder,
            @Value("${nexus.jwt.secret}") String jwtSecret) {
        this.userMapper = userMapper;
        this.organizationUserMapper = organizationUserMapper;
        this.jwtUtils = jwtUtils;
        this.redisTemplate = redisTemplate;
        this.passwordEncoder = passwordEncoder;
        this.secretKey = Keys.hmacShaKeyFor(jwtSecret.getBytes(StandardCharsets.UTF_8));
    }

    // ── Redis Key ────────────────────────────────────────────

    /** nexus:refresh:{userId} */
    private String refreshKey(Long userId) {
        return "nexus:refresh:" + userId;
    }

    /** nexus:blacklist:{jti} */
    private String blacklistKey(String jti) {
        return "nexus:blacklist:" + jti;
    }

    // ── 注册 ─────────────────────────────────────────────────

    @Override
    @Transactional
    public TokenResponse register(RegisterRequest request) {
        // 检查用户名是否已存在
        User existingByUsername = userMapper.findByUsername(request.getUsername());
        if (existingByUsername != null) {
            throw new BizException(ResultCode.PARAM_ERROR, "用户名已存在");
        }

        // 检查邮箱是否已存在（如果提供了邮箱）
        if (request.getEmail() != null && !request.getEmail().isBlank()) {
            User existingByEmail = userMapper.findByEmail(request.getEmail());
            if (existingByEmail != null) {
                throw new BizException(ResultCode.PARAM_ERROR, "邮箱已被使用");
            }
        }

        User user = new User()
                .setUsername(request.getUsername())
                .setEmail(request.getEmail())
                .setNickname(request.getNickname())
                .setPassword(passwordEncoder.encode(request.getPassword()))
                .setRoles("USER")
                .setStatus(1)
                .setPersonalAgentLimit(1)  // 默认配额
                .setOrgCreateLimit(3)
                .setOrgJoinLimit(10);

        userMapper.insert(user);
        log.info("注册成功: username={}, userId={}", request.getUsername(), user.getId());

        return buildTokenResponse(user);
    }

    // ── 登录 ─────────────────────────────────────────────────

    @Override
    public TokenResponse login(LoginRequest request) {
        // 支持用户名或邮箱登录
        User user = userMapper.findByUsernameOrEmail(request.getUsername());

        // 统一错误：不区分"用户不存在"和"密码错误"，避免信息泄露
        if (user == null || !passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new BizException(ResultCode.UNAUTHORIZED, "用户名或密码错误");
        }

        if (user.getStatus() == null || user.getStatus() != 1) {
            throw new BizException(ResultCode.USER_DISABLED);
        }

        return buildTokenResponse(user);
    }

    // ── 刷新 Token ────────────────────────────────────────────

    @Override
    public TokenResponse refresh(String refreshToken) {
        Claims claims;
        try {
            claims = jwtUtils.parseToken(refreshToken);
        } catch (Exception e) {
            throw new BizException(ResultCode.TOKEN_INVALID);
        }

        String userId = claims.get(JwtUtils.CLAIM_USER_ID, String.class);

        if (userId == null) {
            throw new BizException(ResultCode.TOKEN_INVALID);
        }

        // 验证 Redis 中存储的 Refresh Token 是否一致（防止重放）
        String storedToken = redisTemplate.opsForValue()
                .get(refreshKey(Long.valueOf(userId)));
        if (!refreshToken.equals(storedToken)) {
            throw new BizException(ResultCode.TOKEN_INVALID, "Refresh Token 已失效或已被替换");
        }

        User user = userMapper.selectById(Long.valueOf(userId));
        if (user == null || user.getStatus() != 1) {
            throw new BizException(ResultCode.USER_NOT_FOUND);
        }

        return buildTokenResponse(user);
    }

    // ── 登出 ─────────────────────────────────────────────────

    @Override
    public void logout(String accessToken) {
        Claims claims;
        try {
            claims = jwtUtils.parseToken(accessToken);
        } catch (Exception e) {
            log.warn("logout: token parse failed (ignored): {}", e.getMessage());
            return;
        }

        String jti = claims.getId();
        if (jti == null || jti.isBlank()) {
            log.warn("logout: token has no jti, skip blacklist");
            return;
        }

        long remainingMs = claims.getExpiration().getTime() - System.currentTimeMillis();
        if (remainingMs > 0) {
            redisTemplate.opsForValue().set(
                    blacklistKey(jti), "1", remainingMs, TimeUnit.MILLISECONDS);
            log.info("logout: jti={} blacklisted for {}ms", jti, remainingMs);
        }

        // 删除对应 Refresh Token
        String userId = claims.get(JwtUtils.CLAIM_USER_ID, String.class);
        if (userId != null) {
            redisTemplate.delete(refreshKey(Long.valueOf(userId)));
        }
    }

    // ── /me ──────────────────────────────────────────────────

    @Override
    public UserInfoResponse me(String accessToken) {
        Claims claims;
        try {
            claims = jwtUtils.parseToken(accessToken);
        } catch (Exception e) {
            throw new BizException(ResultCode.TOKEN_INVALID);
        }

        // 检查黑名单
        String jti = claims.getId();
        if (jti != null && Boolean.TRUE.equals(redisTemplate.hasKey(blacklistKey(jti)))) {
            throw new BizException(ResultCode.UNAUTHORIZED, "Token 已注销");
        }

        String userId = claims.get(JwtUtils.CLAIM_USER_ID, String.class);
        User user = userMapper.selectById(Long.valueOf(userId));
        if (user == null) {
            throw new BizException(ResultCode.USER_NOT_FOUND);
        }

        // 获取用户加入的组织列表
        List<OrganizationWithRole> organizations = organizationUserMapper.findOrganizationsByUserId(user.getId());

        return UserInfoResponse.builder()
                .userId(user.getId())
                .username(user.getUsername())
                .email(user.getEmail())
                .nickname(user.getNickname())
                .avatar(user.getAvatar())
                .roles(parseRoles(user.getRoles()))
                .personalAgentLimit(user.getPersonalAgentLimit())
                .orgCreateLimit(user.getOrgCreateLimit())
                .orgJoinLimit(user.getOrgJoinLimit())
                .organizations(organizations)
                .build();
    }

    // ── 私有辅助 ──────────────────────────────────────────────

    /**
     * 构建 TokenResponse，同时将 Refresh Token 写入 Redis。
     * Access Token 内嵌 jti（UUID）用于黑名单。
     */
    private TokenResponse buildTokenResponse(User user) {
        List<String> roleList = parseRoles(user.getRoles());
        String userId = String.valueOf(user.getId());
        String jti = UUID.randomUUID().toString();

        // 签发带 jti 的 Access Token
        String accessToken = buildJwtWithJti(userId, roleList, jti, accessTokenExpirationMs);

        // Refresh Token（同样带 jti）
        String refreshJti = UUID.randomUUID().toString();
        String refreshToken = buildJwtWithJti(userId, roleList, refreshJti, refreshTokenExpirationMs);

        // 写入 Redis
        redisTemplate.opsForValue().set(
                refreshKey(user.getId()),
                refreshToken,
                refreshTokenExpirationMs,
                TimeUnit.MILLISECONDS);

        // 获取用户加入的组织列表
        List<OrganizationWithRole> organizations = organizationUserMapper.findOrganizationsByUserId(user.getId());

        // 构建用户信息
        UserInfo userInfo = UserInfo.builder()
                .id(user.getId())
                .username(user.getUsername())
                .email(user.getEmail())
                .nickname(user.getNickname())
                .avatar(user.getAvatar())
                .personalAgentLimit(user.getPersonalAgentLimit())
                .orgCreateLimit(user.getOrgCreateLimit())
                .orgJoinLimit(user.getOrgJoinLimit())
                .build();

        return TokenResponse.builder()
                .accessToken(accessToken)
                .refreshToken(refreshToken)
                .expiresIn(accessTokenExpirationMs / 1000)
                .tokenType("Bearer")
                .user(userInfo)
                .organizations(organizations)
                .build();
    }

    /**
     * 使用 jjwt API 构建带 jti 的 JWT。
     * V5 重构：移除 tenantId claim。
     */
    private String buildJwtWithJti(String userId, List<String> roles, String jti, long expirationMs) {
        Date now = new Date();
        Date expiry = new Date(now.getTime() + expirationMs);

        return Jwts.builder()
                .id(jti)
                .subject(userId)
                .claim(JwtUtils.CLAIM_USER_ID, userId)
                .claim(JwtUtils.CLAIM_ROLES, roles)
                .issuedAt(now)
                .expiration(expiry)
                .signWith(secretKey)
                .compact();
    }

    private List<String> parseRoles(String rolesStr) {
        if (rolesStr == null || rolesStr.isBlank()) {
            return List.of("USER");
        }
        return Arrays.asList(rolesStr.split(","));
    }
}
