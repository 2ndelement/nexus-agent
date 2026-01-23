package tech.nexus.platform.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;

/**
 * 安全配置
 * 
 * 注意：内部服务间通过 Gateway 统一鉴权，
 * 此处主要配置端点安全和 CSRF 防护
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            // 禁用 CSRF（前后端分离）
            .csrf(AbstractHttpConfigurer::disable)
            // 禁用 Session（无状态）
            .sessionManagement(session -> 
                session.sessionCreationPolicy(SessionCreationPolicy.STATELESS)
            )
            // 配置端点权限
            .authorizeHttpRequests(auth -> auth
                // 健康检查端点
                .requestMatchers("/actuator/health", "/health").permitAll()
                // WebSocket 端点
                .requestMatchers("/ws/**").permitAll()
                // 内部服务（由 Gateway 鉴权）
                .requestMatchers("/internal/**").permitAll()
                // 其他请求需要认证
                .anyRequest().authenticated()
            )
            // 添加基础安全头
            .headers(headers -> headers
                .frameOptions(frame -> frame.deny())
                .xssProtection(xss -> xss.enable())
                .contentTypeOptions(content -> {})
            );

        return http.build();
    }
}
