package tech.nexus.platform.common.util;

import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.UUID;

/**
 * 链路追踪工具
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class TraceUtil {

    private final Tracer tracer;

    /**
     * 开始追踪
     */
    public Span startSpan(String operationName) {
        Span span = tracer.spanBuilder(operationName)
                .setSpanKind(SpanKind.SERVER)
                .startSpan();
        return span;
    }

    /**
     * 开始追踪（带父 Span）
     */
    public Span startSpan(String operationName, Span parentSpan) {
        Span span = tracer.spanBuilder(operationName)
                .setParent(io.opentelemetry.context.Context.current().with(parentSpan))
                .setSpanKind(SpanKind.SERVER)
                .startSpan();
        return span;
    }

    /**
     * 记录异常
     */
    public void recordException(Span span, Throwable throwable) {
        span.recordException(throwable);
        span.setStatus(io.opentelemetry.api.trace.StatusCode.ERROR, throwable.getMessage());
    }

    /**
     * 结束追踪
     */
    public void endSpan(Span span) {
        span.end();
    }

    /**
     * 生成追踪ID
     */
    public String generateTraceId() {
        return UUID.randomUUID().toString();
    }

    /**
     * 获取当前 Span
     */
    public Span getCurrentSpan() {
        return Span.current();
    }
}
