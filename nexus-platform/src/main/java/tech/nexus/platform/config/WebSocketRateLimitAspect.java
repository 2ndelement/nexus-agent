package tech.nexus.platform.config;

import com.alibaba.csp.sentinel.Entry;
import com.alibaba.csp.sentinel.SphU;
import com.alibaba.csp.sentinel.slots.block.BlockException;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.springframework.stereotype.Component;

/**
 * WebSocket 限流切面
 */
@Slf4j
@Aspect
@Component
public class WebSocketRateLimitAspect {

    /**
     * 限流资源名
     */
    private static final String WS_MESSAGE_RESOURCE = "websocket:message";

    /**
     * 消息处理限流
     */
    @Around("execution(* tech.nexus.platform.adapter.webchat.handler.WebChatWebSocketHandler.handleTextMessage(..))")
    public Object rateLimitMessage(ProceedingJoinPoint joinPoint) throws Throwable {
        Entry entry = null;
        try {
            entry = SphU.entry(WS_MESSAGE_RESOURCE);
            return joinPoint.proceed();
        } catch (BlockException e) {
            log.warn("[Sentinel] WebSocket 消息限流触发");
            return null;
        } finally {
            if (entry != null) {
                entry.exit();
            }
        }
    }
}
