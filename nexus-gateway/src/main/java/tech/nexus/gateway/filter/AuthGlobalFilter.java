package tech.nexus.gateway.filter;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;
import tech.nexus.common.constant.NexusConstants;
import tech.nexus.common.utils.JwtUtils;
import tech.nexus.gateway.config.WhiteListConfig;

import java.util.List;

/**
 * JWT 全局鉴权过滤器（order = -100，在其他 Filter 之前执行）。
 *
 * <p>处理逻辑：
 * <ol>
 *   <li>白名单路径 → 直接放行</li>
 *   <li>提取 {@code Authorization: Bearer <token>}</li>
 *   <li>本地验证 Token 有效性（不调用远程）</li>
 *   <li>检查 JWT jti 是否在 Redis 黑名单中（已登出）</li>
 *   <li>从 Token 提取 {@code tenantId / userId / roles}</li>
 *   <li>注入下游 Header：{@code X-Tenant-Id / X-User-Id / X-Roles}</li>
 * </ol>
 *
 * <p>Token 无效或过期时，返回 HTTP 200 + JSON body（遵循 nexus-common Result 规范）。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AuthGlobalFilter implements GlobalFilter, Ordered {

    /** Header 名：透传给下游的用户 ID */
    public static final String HEADER_USER_ID  = "X-User-Id";

    /** Header 名：透传给下游的角色列表（逗号分隔） */
    public static final String HEADER_ROLES    = "X-Roles";

    private final JwtUtils jwtUtils;
    private final WhiteListConfig whiteListConfig;
    private final StringRedisTemplate redisTemplate;

    @Override
    public int getOrder() {
        return -100;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String path = exchange.getRequest().getPath().value();

        // 1. 白名单直接放行
        if (whiteListConfig.isWhiteListed(path)) {
            log.debug("whitelist pass: {}", path);
            return chain.filter(exchange);
        }

        // 2. 提取 Authorization Header
        String authHeader = exchange.getRequest().getHeaders()
                .getFirst(NexusConstants.HEADER_AUTHORIZATION);

        if (authHeader == null || !authHeader.startsWith(NexusConstants.BEARER_PREFIX)) {
            log.warn("missing or invalid Authorization header: path={}", path);
            return unauthorized(exchange, "缺少认证 Token");
        }

        String token = authHeader.substring(NexusConstants.BEARER_PREFIX.length()).trim();

        // 3. 解析并验证 Token
        Claims claims;
        try {
            claims = jwtUtils.parseToken(token);
        } catch (JwtException e) {
            log.warn("invalid token: path={}, error={}", path, e.getMessage());
            return unauthorized(exchange, "Token 无效或已过期");
        } catch (Exception e) {
            log.error("token parse unexpected error: path={}", path, e);
            return unauthorized(exchange, "Token 解析失败");
        }

        // 4. 黑名单检查：已登出的 Token 直接拒绝
        String jti = claims.getId();
        if (jti != null && !jti.isBlank()) {
            String blacklistKey = "nexus:blacklist:" + jti;
            String blocked = redisTemplate.opsForValue().get(blacklistKey);
            if (blocked != null) {
                log.warn("token blacklisted: jti={}, path={}", jti, path);
                return unauthorized(exchange, "Token 已失效（已登出）");
            }
        }

        // 5. 提取 claims
        String userId   = claims.get(JwtUtils.CLAIM_USER_ID,   String.class);
        String tenantId = claims.get(JwtUtils.CLAIM_TENANT_ID, String.class);

        @SuppressWarnings("unchecked")
        List<String> roles = claims.get(JwtUtils.CLAIM_ROLES, List.class);
        String rolesStr = (roles != null) ? String.join(",", roles) : "";

        // 6. 构造注入了鉴权信息的下游请求
        // V5: 新 JWT 可能不再携带 tenantId，此时保留前端传入的 X-Tenant-Id / X-Context，避免覆盖为空
        ServerHttpRequest.Builder requestBuilder = exchange.getRequest().mutate()
                .header(HEADER_USER_ID, userId != null ? userId : "")
                .header(HEADER_ROLES, rolesStr);

        if (tenantId != null && !tenantId.isBlank()) {
            requestBuilder.header(NexusConstants.HEADER_TENANT_ID, tenantId);
        }

        ServerHttpRequest mutatedRequest = requestBuilder
                // 移除原始 Authorization，避免下游重复处理（可按需保留）
                // .headers(h -> h.remove(NexusConstants.HEADER_AUTHORIZATION))
                .build();

        log.debug("auth pass: path={}, userId={}, tenantId={}", path, userId, tenantId);
        return chain.filter(exchange.mutate().request(mutatedRequest).build());
    }

    // ── 私有辅助 ──────────────────────────────────────────────

    /**
     * 返回 401 响应（JSON 格式，遵循 Result 规范）。
     * HTTP 状态码使用 401，Body 是标准 JSON。
     */
    private Mono<Void> unauthorized(ServerWebExchange exchange, String message) {
        ServerHttpResponse response = exchange.getResponse();
        response.setStatusCode(HttpStatus.UNAUTHORIZED);
        response.getHeaders().setContentType(MediaType.APPLICATION_JSON);

        // {"code":401,"msg":"<message>","data":null}
        String body = String.format(
                "{\"code\":401,\"msg\":\"%s\",\"data\":null}",
                message.replace("\"", "\\\""));

        var buffer = response.bufferFactory().wrap(body.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        return response.writeWith(Mono.just(buffer));
    }
}
