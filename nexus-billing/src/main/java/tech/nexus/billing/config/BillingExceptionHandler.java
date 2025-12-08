package tech.nexus.billing.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import tech.nexus.billing.controller.BillingController.QuotaExceededException;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.Result;
import tech.nexus.common.result.ResultCode;

import java.util.stream.Collectors;

/**
 * 计费服务全局异常处理器
 */
@Slf4j
@RestControllerAdvice
public class BillingExceptionHandler {

    @ExceptionHandler(QuotaExceededException.class)
    public ResponseEntity<Result<Object>> handleQuotaExceeded(QuotaExceededException ex) {
        log.warn("配额超限: {}", ex.getMessage());
        Result<Object> result = Result.fail(429, ex.getMessage());
        return ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS).body(result);
    }

    @ExceptionHandler(BizException.class)
    public ResponseEntity<Result<Object>> handleBizException(BizException ex) {
        log.warn("业务异常: code={} msg={}", ex.getCode(), ex.getMessage());
        HttpStatus status = switch (ex.getCode()) {
            case 401 -> HttpStatus.UNAUTHORIZED;
            case 403 -> HttpStatus.FORBIDDEN;
            case 404 -> HttpStatus.NOT_FOUND;
            case 429 -> HttpStatus.TOO_MANY_REQUESTS;
            default  -> ex.getCode() >= 400 && ex.getCode() < 500
                    ? HttpStatus.BAD_REQUEST
                    : HttpStatus.INTERNAL_SERVER_ERROR;
        };
        return ResponseEntity.status(status).body(Result.fail(ex.getCode(), ex.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Result<Object>> handleValidation(MethodArgumentNotValidException ex) {
        String msg = ex.getBindingResult().getFieldErrors().stream()
                .map(FieldError::getDefaultMessage)
                .collect(Collectors.joining("; "));
        log.warn("参数校验失败: {}", msg);
        return ResponseEntity.badRequest().body(Result.fail(ResultCode.PARAM_ERROR.getCode(), msg));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Result<Object>> handleException(Exception ex) {
        log.error("未预期异常", ex);
        return ResponseEntity.internalServerError()
                .body(Result.fail(ResultCode.INTERNAL_ERROR));
    }
}
