package tech.nexus.common.exception;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import tech.nexus.common.result.ResultCode;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@DisplayName("BizException 单元测试")
class BizExceptionTest {

    // ── 构造函数：ResultCode ──────────────────────────────────

    @Test
    @DisplayName("BizException(ResultCode) 应正确设置 code 和 message")
    void constructor_with_result_code() {
        BizException ex = new BizException(ResultCode.USER_NOT_FOUND);

        assertThat(ex.getCode()).isEqualTo(2001);
        assertThat(ex.getMessage()).isEqualTo("用户不存在");
    }

    @Test
    @DisplayName("BizException(ResultCode.TOKEN_EXPIRED) 应正确设置 3001")
    void constructor_token_expired() {
        BizException ex = new BizException(ResultCode.TOKEN_EXPIRED);

        assertThat(ex.getCode()).isEqualTo(3001);
        assertThat(ex.getMessage()).isEqualTo("Token 已过期");
    }

    // ── 构造函数：ResultCode + 自定义 msg ─────────────────────

    @Test
    @DisplayName("BizException(ResultCode, msg) 应覆盖默认消息但保留 code")
    void constructor_with_result_code_and_custom_msg() {
        BizException ex = new BizException(ResultCode.PARAM_ERROR, "字段 email 格式不正确");

        assertThat(ex.getCode()).isEqualTo(400);
        assertThat(ex.getMessage()).isEqualTo("字段 email 格式不正确");
    }

    // ── 构造函数：自定义 code + msg ───────────────────────────

    @Test
    @DisplayName("BizException(code, msg) 应正确设置自定义 code 和 message")
    void constructor_with_custom_code_and_msg() {
        BizException ex = new BizException(9527, "自定义业务错误");

        assertThat(ex.getCode()).isEqualTo(9527);
        assertThat(ex.getMessage()).isEqualTo("自定义业务错误");
    }

    // ── 是否继承 RuntimeException ─────────────────────────────

    @Test
    @DisplayName("BizException 应是 RuntimeException 的子类")
    void is_runtime_exception() {
        BizException ex = new BizException(ResultCode.FORBIDDEN);
        assertThat(ex).isInstanceOf(RuntimeException.class);
    }

    // ── 抛出与捕获 ────────────────────────────────────────────

    @Test
    @DisplayName("抛出 BizException 后可以被正确捕获并读取 code")
    void throw_and_catch_biz_exception() {
        assertThatThrownBy(() -> {
            throw new BizException(ResultCode.UNAUTHORIZED);
        })
                .isInstanceOf(BizException.class)
                .satisfies(e -> {
                    BizException biz = (BizException) e;
                    assertThat(biz.getCode()).isEqualTo(401);
                    assertThat(biz.getMessage()).isEqualTo("未认证");
                });
    }
}
