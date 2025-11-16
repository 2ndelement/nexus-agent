package tech.nexus.auth.config;

import org.springframework.context.annotation.Configuration;

/**
 * Redis 配置。
 *
 * <p>使用 Spring Boot 自动配置提供的 {@code StringRedisTemplate}（key/value 均为 String），
 * 无需额外定义 Bean，保持唯一性方便测试 Mock。
 */
@Configuration
public class RedisConfig {
    // Spring Boot Auto-Configure 已自动注册 StringRedisTemplate
    // 此处保留空类供后续扩展（如连接池参数）
}
