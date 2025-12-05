package tech.nexus.gateway.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;
import org.springframework.util.AntPathMatcher;

import java.util.List;

/**
 * JWT 鉴权白名单配置。
 *
 * <p>白名单路径直接放行，不做 Token 校验。
 * 路径支持 Ant 风格通配符（如 {@code /api/auth/**}）。
 *
 * <p>配置示例（application.yml）：
 * <pre>
 * nexus:
 *   gateway:
 *     white-list:
 *       - /api/auth/**
 *       - /actuator/health
 * </pre>
 */
@Configuration
@ConfigurationProperties(prefix = "nexus.gateway")
public class WhiteListConfig {

    /**
     * 默认白名单（代码层兜底，即使 yml 未配置也生效）。
     */
    private List<String> whiteList = List.of(
            "/api/auth/**",
            "/actuator/health",
            "/actuator/info"
    );

    private static final AntPathMatcher PATH_MATCHER = new AntPathMatcher();

    public List<String> getWhiteList() {
        return whiteList;
    }

    public void setWhiteList(List<String> whiteList) {
        this.whiteList = whiteList;
    }

    /**
     * 判断给定路径是否在白名单内。
     *
     * @param path 请求路径（如 {@code /api/auth/login}）
     * @return {@code true} 表示在白名单，不需要 Token
     */
    public boolean isWhiteListed(String path) {
        return whiteList.stream()
                .anyMatch(pattern -> PATH_MATCHER.match(pattern, path));
    }
}
