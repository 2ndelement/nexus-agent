package tech.nexus.common.sentinel;

import com.alibaba.csp.sentinel.slots.block.BlockException;
import lombok.extern.slf4j.Slf4j;

import java.util.Map;

/**
 * Sentinel 限流降级通用 fallback 处理器。
 *
 * <p>业务服务使用 @SentinelResource 注解时，
 * 将 blockHandler 指向此类的静态方法。
 *
 * <p>示例：
 * <pre>{@code
 * @SentinelResource(value = "login", blockHandler = "handleBlock",
 *                   blockHandlerClass = SentinelFallbackHandler.class)
 * public R<LoginVO> login(LoginDTO dto) { ... }
 * }</pre>
 */
@Slf4j
public class SentinelFallbackHandler {

    /**
     * 通用限流降级方法（返回 Map，兼容 @RestController）。
     *
     * <p>注意：blockHandler 方法必须是 public static，
     * 参数列表与原方法一致，末尾追加 BlockException。
     */
    public static Map<String, Object> handleBlock(BlockException ex) {
        log.warn("[Sentinel] 请求被限流: rule={}, resource={}",
                ex.getRule(), ex.getRule() != null ? ex.getRule().getResource() : "unknown");
        return Map.of(
                "code", 429,
                "msg", "请求过于频繁，请稍后重试",
                "data", Map.of()
        );
    }

    /**
     * 通用熔断降级方法。
     */
    public static Map<String, Object> handleFallback(Throwable ex) {
        log.error("[Sentinel] 服务降级: {}", ex.getMessage());
        return Map.of(
                "code", 503,
                "msg", "服务暂时不可用，请稍后重试",
                "data", Map.of()
        );
    }
}
