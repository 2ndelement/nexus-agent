package tech.nexus.session.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.Data;

/**
 * 追加消息请求 DTO。
 */
@Data
public class AppendMessageRequest {

    /**
     * 消息角色：user / assistant / system / tool
     */
    @NotBlank(message = "role 不能为空")
    @Pattern(regexp = "user|assistant|system|tool", message = "role 只能是 user/assistant/system/tool")
    private String role;

    /** 消息内容，不能为空 */
    @NotBlank(message = "content 不能为空")
    private String content;

    /** token 消耗数（可选） */
    private Integer tokens;

    /** 附加元数据 JSON 字符串（可选） */
    private String metadata;

    /**
     * 幂等 Key，调用方提供，用于防止重复写入。
     * 建议格式：{convId}:{msgId} 或 UUID。
     */
    private String idempotentKey;
}
