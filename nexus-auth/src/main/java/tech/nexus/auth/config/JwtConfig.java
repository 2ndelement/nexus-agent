package tech.nexus.auth.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import tech.nexus.common.utils.JwtUtils;

/**
 * JWT 配置类。
 * 密钥从 application.yml 的 nexus.jwt.secret 读取，不硬编码。
 */
@Configuration
public class JwtConfig {

    @Value("${nexus.jwt.secret}")
    private String secret;

    @Value("${nexus.jwt.access-token-expiration-ms:7200000}")
    private long accessTokenExpirationMs;

    @Bean
    public JwtUtils jwtUtils() {
        return new JwtUtils(secret, accessTokenExpirationMs);
    }
}
