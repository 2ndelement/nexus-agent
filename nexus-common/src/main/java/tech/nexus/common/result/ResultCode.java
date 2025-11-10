package tech.nexus.common.result;

import lombok.Getter;

/**
 * 统一错误码枚举
 */
@Getter
public enum ResultCode {

    // ── 通用 ──────────────────────────────────────────────
    SUCCESS(200, "操作成功"),
    PARAM_ERROR(400, "参数错误"),
    UNAUTHORIZED(401, "未认证"),
    FORBIDDEN(403, "无权限"),
    NOT_FOUND(404, "资源不存在"),
    INTERNAL_ERROR(500, "服务器内部错误"),

    // ── 租户 1xxx ─────────────────────────────────────────
    TENANT_NOT_FOUND(1001, "租户不存在"),
    TENANT_DISABLED(1002, "租户已禁用"),

    // ── 用户 2xxx ─────────────────────────────────────────
    USER_NOT_FOUND(2001, "用户不存在"),
    USER_DISABLED(2002, "用户已禁用"),

    // ── Token 3xxx ────────────────────────────────────────
    TOKEN_EXPIRED(3001, "Token 已过期"),
    TOKEN_INVALID(3002, "Token 无效");

    private final int code;
    private final String msg;

    ResultCode(int code, String msg) {
        this.code = code;
        this.msg = msg;
    }
}
