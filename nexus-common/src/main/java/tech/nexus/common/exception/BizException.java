package tech.nexus.common.exception;

import lombok.Getter;
import tech.nexus.common.result.ResultCode;

/**
 * 业务异常。
 *
 * <p>所有可预期的业务错误应抛出此异常，由全局处理器统一转换为 {@link tech.nexus.common.result.Result}。
 */
@Getter
public class BizException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    private final int code;

    /**
     * 使用预定义错误码构建异常。
     *
     * @param resultCode 错误码枚举
     */
    public BizException(ResultCode resultCode) {
        super(resultCode.getMsg());
        this.code = resultCode.getCode();
    }

    /**
     * 使用预定义错误码构建异常，并覆盖默认消息。
     *
     * @param resultCode 错误码枚举
     * @param msg        自定义消息
     */
    public BizException(ResultCode resultCode, String msg) {
        super(msg);
        this.code = resultCode.getCode();
    }

    /**
     * 使用自定义 code 与消息构建异常。
     *
     * @param code 错误码
     * @param msg  错误信息
     */
    public BizException(int code, String msg) {
        super(msg);
        this.code = code;
    }
}
