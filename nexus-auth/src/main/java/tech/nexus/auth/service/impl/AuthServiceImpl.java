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
import tech.nexus.auth.dto.UserInfoResponse;
import tech.nexus.auth.entity.User;
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
 * <p>Access Token 内嵌 {@code jti}（UUID），用于登出后加入 Redis 黑名单。
 * Refresh Token 存入 Redis，key = {@code nexus:{tenantId}:refresh:{userId}}。
 * 黑名单 key = {@code nexus:blacklist:{jti}}。
 */
@Slf4j
@Service
public class AuthServiceImpl implements AuthService {

    private final UserMapper userMapper;
    private final JwtUtils jwtUtils;           // 用于解析 token（验签）
    private final StringRedisTemplate redisTemplate;
    private final BCryptPasswordEncoder passwordEncoder;
    private final SecretKey secretKey;         // 用于签发带 jti 的 access token

    @Value("${nexus.jwt.access-token-expiration-ms:7200000}")
    private long accessTokenExpirationMs;

    @Value("${nexus.jwt.refresh-token-expiration-ms:2592000000}")
    private long refreshTokenExpirationMs;

    public AuthServiceImpl(
            UserMapper userMapper,
            JwtUtils jwtUtils,
            StringRedisTemplate redisTemplate,
            BCryptPasswordEncoder passwordEncoder,
            @Value("${nexus.jwt.secret}") String jwtSecret) {
        this.userMapper = userMapper;
        this.jwtUtils = jwtUtils;
        this.redisTemplate = redisTemplate;
        this.passwordEncoder = passwordEncoder;
        this.secretKey = Keys.hmacShaKeyFor(jwtSecret.getBytes(StandardCharsets.UTF_8));
    }

    // ── Redis Key ────────────────────────────────────────────

    /** nexus:{tenantId}:refresh:{userId} */
    private String refreshKey(Long tenantId, Long userId) {
        return "nexus:" + tenantId + ":refresh:" + userId;
    }

    /** nexus:blacklist:{jti} */
    private String blacklistKey(String jti) {
        return "nexus:blacklist:" + jti;
    }

    // ── 注册 ─────────────────────────────────────────────────

    @Override
    @Transactional
    public TokenResponse register(RegisterRequest request) {
        User existing = userMapper.findByTenantIdAndUsername(
                request.getTenantId(), request.getUsername());
        if (existing != null) {
            throw new BizException(ResultCode.PARAM_ERROR, "用户名已存在");
        }

        User user = new User()
                .setTenantId(request.getTenantId())
                .setUsername(request.getUsername())
                .setEmail(request.getEmail())
                .setPassword(passwordEncoder.encode(request.getPassword()))
                .setRoles("USER")
                .setStatus(1);

        userMapper.insert(user);
        log.info("注册成功: tenantId={}, username={}, userId={}",
                request.getTenantId(), request.getUsername(), user.getId());

        return buildTokenResponse(user);
    }

    // ── 登录 ─────────────────────────────────────────────────

    @Override
    public TokenResponse login(LoginRequest request) {
        User user = userMapper.findByTenantIdAndUsername(
                request.getTenantId(), request.getUsername());

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
        String tenantId = claims.get(JwtUtils.CLAIM_TENANT_ID, String.class);

        if (userId == null || tenantId == null) {
            throw new BizException(ResultCode.TOKEN_INVALID);
        }

        // 验证 Redis 中存储的 Refresh Token 是否一致（防止重放）
        String storedToken = redisTemplate.opsForValue()
                .get(refreshKey(Long.valueOf(tenantId), Long.valueOf(userId)));
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
        String tenantId = claims.get(JwtUtils.CLAIM_TENANT_ID, String.class);
        if (userId != null && tenantId != null) {
            redisTemplate.delete(refreshKey(Long.valueOf(tenantId), Long.valueOf(userId)));
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

        return UserInfoResponse.builder()
                .userId(user.getId())
                .tenantId(user.getTenantId())
                .username(user.getUsername())
                .email(user.getEmail())
                .roles(parseRoles(user.getRoles()))
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
        String tenantId = String.valueOf(user.getTenantId());
        String jti = UUID.randomUUID().toString();

        // 签发带 jti 的 Access Token
        String accessToken = buildJwtWithJti(userId, tenantId, roleList, jti, accessTokenExpirationMs);

        // Refresh Token（同样带 jti）
        String refreshJti = UUID.randomUUID().toString();
        String refreshToken = buildJwtWithJti(userId, tenantId, roleList, refreshJti, refreshTokenExpirationMs);

        // 写入 Redis
        redisTemplate.opsForValue().set(
                refreshKey(user.getTenantId(), user.getId()),
                refreshToken,
                refreshTokenExpirationMs,
                TimeUnit.MILLISECONDS);

        return TokenResponse.builder()
                .accessToken(accessToken)
                .refreshToken(refreshToken)
                .expiresIn(accessTokenExpirationMs / 1000)
                .tokenType("Bearer")
                .build();
    }

    /**
     * 使用 jjwt API 构建带 jti 的 JWT（与 JwtUtils 共用同一密钥，因此 JwtUtils 可解析）。
     */
    private String buildJwtWithJti(String userId, String tenantId,
                                    List<String> roles, String jti, long expirationMs) {
        Date now = new Date();
        Date expiry = new Date(now.getTime() + expirationMs);

        return Jwts.builder()
                .id(jti)
                .subject(userId)
                .claim(JwtUtils.CLAIM_USER_ID, userId)
                .claim(JwtUtils.CLAIM_TENANT_ID, tenantId)
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
