package tech.nexus.common.result;

import lombok.Getter;
import lombok.ToString;

import java.io.Serializable;

/**
 * 统一 API 响应结构
 *
 * @param <T> 响应数据类型
 */
@Getter
@ToString
public class Result<T> implements Serializable {

    private static final long serialVersionUID = 1L;

    private final int code;
    private final String msg;
    private final T data;

    private Result(int code, String msg, T data) {
        this.code = code;
        this.msg = msg;
        this.data = data;
    }

    // ── 成功 ────────────────────────────────────────────

    public static <T> Result<T> success(T data) {
        return new Result<>(ResultCode.SUCCESS.getCode(), ResultCode.SUCCESS.getMsg(), data);
    }

    public static <T> Result<T> success() {
        return success(null);
    }

    // ── 失败 ────────────────────────────────────────────

    public static <T> Result<T> fail(ResultCode resultCode) {
        return new Result<>(resultCode.getCode(), resultCode.getMsg(), null);
    }

    public static <T> Result<T> fail(int code, String msg) {
        return new Result<>(code, msg, null);
    }

    // ── 便捷判断 ─────────────────────────────────────────

    public boolean isSuccess() {
        return this.code == ResultCode.SUCCESS.getCode();
    }
}
