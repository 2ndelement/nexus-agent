package tech.nexus.gateway.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import tech.nexus.common.utils.JwtUtils;

/**
 * 网关侧 JWT 配置。
 *
 * <p>密钥须与 nexus-auth 使用同一个值（共享密钥模式，HMAC-SHA）。
 * 生产环境通过环境变量 {@code NEXUS_JWT_SECRET} 注入，
 * 开发环境在 application.yml 中配置默认值。
 */
@Configuration
public class JwtConfig {

    @Value("${nexus.jwt.secret}")
    private String secret;

    /**
     * expirationMs 在 Gateway 侧仅供 JwtUtils 构造使用，
     * 不影响验证逻辑（Token 过期由 jjwt 解析时自动检测）。
     */
    @Value("${nexus.jwt.expiration-ms:7200000}")
    private long expirationMs;

    @Bean
    public JwtUtils jwtUtils() {
        return new JwtUtils(secret, expirationMs);
    }
}
