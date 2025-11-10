package tech.nexus.common.result;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

@DisplayName("Result<T> 单元测试")
class ResultTest {

    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        objectMapper = new ObjectMapper();
    }

    // ── success() ────────────────────────────────────────────

    @Test
    @DisplayName("Result.success() 序列化应为 {\"code\":200,\"msg\":\"操作成功\",\"data\":null}")
    void success_no_data_serializes_correctly() throws Exception {
        Result<Void> result = Result.success();

        String json = objectMapper.writeValueAsString(result);
        JsonNode node = objectMapper.readTree(json);

        assertThat(node.get("code").asInt()).isEqualTo(200);
        assertThat(node.get("msg").asText()).isEqualTo("操作成功");
        assertThat(node.get("data").isNull()).isTrue();
    }

    @Test
    @DisplayName("Result.success(data) 序列化应包含 data 字段")
    void success_with_data_serializes_correctly() throws Exception {
        Result<String> result = Result.success("hello");

        String json = objectMapper.writeValueAsString(result);
        JsonNode node = objectMapper.readTree(json);

        assertThat(node.get("code").asInt()).isEqualTo(200);
        assertThat(node.get("data").asText()).isEqualTo("hello");
    }

    @Test
    @DisplayName("Result.success() isSuccess() 应返回 true")
    void success_isSuccess_returns_true() {
        assertThat(Result.success().isSuccess()).isTrue();
    }

    // ── fail() ────────────────────────────────────────────────

    @Test
    @DisplayName("Result.fail(ResultCode) 应包含正确 code 和 msg")
    void fail_with_result_code_has_correct_code_and_msg() {
        Result<Void> result = Result.fail(ResultCode.UNAUTHORIZED);

        assertThat(result.getCode()).isEqualTo(401);
        assertThat(result.getMsg()).isEqualTo("未认证");
        assertThat(result.getData()).isNull();
        assertThat(result.isSuccess()).isFalse();
    }

    @Test
    @DisplayName("Result.fail(code, msg) 应包含自定义 code 和 msg")
    void fail_with_custom_code_msg() {
        Result<Void> result = Result.fail(9999, "自定义错误");

        assertThat(result.getCode()).isEqualTo(9999);
        assertThat(result.getMsg()).isEqualTo("自定义错误");
    }

    @Test
    @DisplayName("Result.fail(ResultCode.TENANT_NOT_FOUND) 应为 1001")
    void fail_tenant_not_found() {
        Result<Void> result = Result.fail(ResultCode.TENANT_NOT_FOUND);

        assertThat(result.getCode()).isEqualTo(1001);
        assertThat(result.getMsg()).isEqualTo("租户不存在");
    }

    @Test
    @DisplayName("Result.fail(ResultCode.TOKEN_EXPIRED) 应为 3001")
    void fail_token_expired() {
        Result<Void> result = Result.fail(ResultCode.TOKEN_EXPIRED);

        assertThat(result.getCode()).isEqualTo(3001);
        assertThat(result.getMsg()).isEqualTo("Token 已过期");
    }

    // ── ResultCode 完整性 ─────────────────────────────────────

    @Test
    @DisplayName("ResultCode 枚举不应有重复 code 值")
    void result_code_no_duplicate_codes() {
        ResultCode[] values = ResultCode.values();
        long distinctCount = java.util.Arrays.stream(values)
                .mapToInt(ResultCode::getCode)
                .distinct()
                .count();
        assertThat(distinctCount).isEqualTo(values.length);
    }

    // ── PageResult ────────────────────────────────────────────

    @Test
    @DisplayName("PageResult.of() 总页数计算应正确")
    void page_result_pages_calculation() {
        PageResult<String> page = PageResult.of(
                java.util.List.of("a", "b", "c"), 25L, 1, 10);

        assertThat(page.getTotal()).isEqualTo(25L);
        assertThat(page.getPages()).isEqualTo(3);
        assertThat(page.getPage()).isEqualTo(1);
        assertThat(page.getSize()).isEqualTo(10);
        assertThat(page.getRecords()).hasSize(3);
    }
}
