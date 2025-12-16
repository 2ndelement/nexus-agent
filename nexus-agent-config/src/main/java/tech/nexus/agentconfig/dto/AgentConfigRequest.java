package tech.nexus.agentconfig.dto;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.math.BigDecimal;
import java.util.List;

/**
 * 创建/更新 Agent 请求 DTO。
 */
@Data
public class AgentConfigRequest {

    /** Agent 名称 */
    @NotBlank(message = "Agent 名称不能为空")
    @Size(max = 100, message = "Agent 名称最长 100 字符")
    private String name;

    /** 描述 */
    private String description;

    /** 头像 URL */
    @Size(max = 500)
    private String avatar;

    /**
     * 系统提示词（最大 64KB ≈ 65536 字符）。
     * 注：@Size 按字符长度校验，UTF-8 字节数可能超过 65536，业务层再做精确校验。
     */
    @Size(max = 65536, message = "system_prompt 超过 64KB 限制")
    private String systemPrompt;

    /** 使用模型 */
    private String model;

    /** 温度参数：0.0 ~ 2.0 */
    @DecimalMin(value = "0.0", message = "temperature 不能小于 0.0")
    @DecimalMax(value = "2.0", message = "temperature 不能大于 2.0")
    private BigDecimal temperature;

    /** 最大 token 数 */
    private Integer maxTokens;

    /** 启用的工具名称列表 */
    private List<String> tools;

    /** 绑定的知识库 ID 列表 */
    private List<Long> kbIds;

    /** 状态：1=发布 0=草稿 */
    private Integer status;

    /** 是否为平台公共模板 */
    private Integer isPublic;

    /** 变更说明（用于历史版本记录） */
    private String changeNote;
}
