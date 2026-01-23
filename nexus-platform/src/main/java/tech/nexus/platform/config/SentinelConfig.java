package tech.nexus.platform.config;

import com.alibaba.csp.sentinel.adapter.spring.webmvc.callback.BlockExceptionHandler;
import com.alibaba.csp.sentinel.slots.block.authority.AuthorityException;
import com.alibaba.csp.sentinel.slots.block.degrade.DegradeException;
import com.alibaba.csp.sentinel.slots.block.flow.FlowException;
import com.alibaba.csp.sentinel.slots.block.param.ParamException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import tech.nexus.platform.common.result.Result;

import java.util.Map;

/**
 * Sentinel 配置 - 限流、熔断、降级
 */
@Slf4j
@Configuration
public class SentinelConfig {

    private final ObjectMapper objectMapper;

    public SentinelConfig(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    /**
     * Web 限流异常处理
     */
    @Bean
    public BlockExceptionHandler blockExceptionHandler() {
        return new BlockExceptionHandler() {
            @Override
            public void handle(HttpServletRequest request, HttpServletResponse response, 
                             Exception e) throws Exception {
                
                String message;
                int code;
                HttpStatus status = HttpStatus.TOO_MANY_REQUESTS;

                if (e instanceof FlowException) {
                    message = "请求过于频繁，请稍后再试";
                    code = 429001;
                    log.warn("[Sentinel] 触发限流: {}", request.getRequestURI());
                } else if (e instanceof DegradeException) {
                    message = "服务暂时不可用，请稍后再试";
                    code = 503001;
                    log.warn("[Sentinel] 触发熔断: {}", request.getRequestURI());
                } else if (e instanceof AuthorityException) {
                    message = "访问被拒绝";
                    code = 403001;
                } else if (e instanceof ParamException) {
                    message = "参数访问过于频繁";
                    code = 429002;
                } else {
                    message = "系统繁忙，请稍后再试";
                    code = 500001;
                }

                response.setStatus(status.value());
                response.setContentType(MediaType.APPLICATION_JSON_VALUE);
                response.setCharacterEncoding("UTF-8");
                
                Result<?> result = Result.fail(code, message);
                objectMapper.writeValue(response.getOutputStream(), result);
            }
        };
    }
}
