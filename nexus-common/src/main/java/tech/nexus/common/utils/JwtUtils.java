package tech.nexus.common.utils;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.List;
import java.util.Objects;

/**
 * JWT 工具类（签发 / 解析 / 验证）。
 *
 * <p>密钥通过构造参数传入，<strong>不硬编码</strong>。
 * 调用方通常在 Spring 配置类中将本实例声明为 Bean，
 * 密钥值从 {@code application.yml} 的 {@code nexus.jwt.secret} 读取。
 *
 * <pre>{@code
 * @Bean
 * public JwtUtils jwtUtils(
 *         @Value("${nexus.jwt.secret}") String secret,
 *         @Value("${nexus.jwt.expiration-ms:86400000}") long expirationMs) {
 *     return new JwtUtils(secret, expirationMs);
 * }
 * }</pre>
 */
public final class JwtUtils {

    /** Claims key：用户 ID */
    public static final String CLAIM_USER_ID = "userId";

    /** Claims key：租户 ID */
    public static final String CLAIM_TENANT_ID = "tenantId";

    /** Claims key：角色列表 */
    public static final String CLAIM_ROLES = "roles";

    private final SecretKey secretKey;
    private final long expirationMs;

    /**
     * @param secretKey    HMAC-SHA 密钥字符串，建议 ≥ 256 bit（32 字符）
     * @param expirationMs Token 有效时长（毫秒）
     */
    public JwtUtils(String secretKey, long expirationMs) {
        Objects.requireNonNull(secretKey, "JWT secretKey must not be null");
        if (secretKey.isBlank()) {
            throw new IllegalArgumentException("JWT secretKey must not be blank");
        }
        this.secretKey = Keys.hmacShaKeyFor(secretKey.getBytes(StandardCharsets.UTF_8));
        this.expirationMs = expirationMs;
    }

    /**
     * 生成 JWT Token。
     *
     * @param userId   用户 ID
     * @param tenantId 租户 ID
     * @param roles    角色列表
     * @return 签名后的 JWT 字符串
     */
    public String generateToken(String userId, String tenantId, List<String> roles) {
        Objects.requireNonNull(userId, "userId must not be null");
        Objects.requireNonNull(tenantId, "tenantId must not be null");

        Date now = new Date();
        Date expiry = new Date(now.getTime() + expirationMs);

        return Jwts.builder()
                .subject(userId)
                .claim(CLAIM_USER_ID, userId)
                .claim(CLAIM_TENANT_ID, tenantId)
                .claim(CLAIM_ROLES, roles)
                .issuedAt(now)
                .expiration(expiry)
                .signWith(secretKey)
                .compact();
    }

    /**
     * 解析 Token，返回 Claims。
     *
     * @param token JWT 字符串
     * @return Claims
     * @throws io.jsonwebtoken.ExpiredJwtException  Token 已过期
     * @throws io.jsonwebtoken.MalformedJwtException Token 格式错误
     * @throws io.jsonwebtoken.security.SignatureException Token 签名无效（被篡改）
     */
    public Claims parseToken(String token) {
        return Jwts.parser()
                .verifyWith(secretKey)
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    /**
     * 判断 Token 是否已过期。
     *
     * <p>若 Token 签名无效（被篡改），视同过期，返回 {@code true}。
     *
     * @param token JWT 字符串
     * @return {@code true} 表示已过期或无效
     */
    public boolean isExpired(String token) {
        try {
            Claims claims = parseToken(token);
            return claims.getExpiration().before(new Date());
        } catch (ExpiredJwtException e) {
            return true;
        } catch (JwtException e) {
            // 签名错误、格式错误等均视为无效
            return true;
        }
    }
}
