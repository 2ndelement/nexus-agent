package tech.nexus.knowledge.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 创建知识库请求 DTO。
 */
@Data
public class CreateKbRequest {

    @NotBlank(message = "知识库名称不能为空")
    @Size(max = 100, message = "知识库名称最多100字符")
    private String name;

    @Size(max = 500, message = "描述最多500字符")
    private String description;

    /**
     * 知识库类型：GENERAL / QA / CODE，默认 GENERAL
     */
    private String type;

    /**
     * Embedding 模型，默认 sentence-transformers
     */
    private String embedModel;

    /**
     * 分片策略配置（JSON 字符串），可选
     * 示例：{"chunkSize":500,"chunkOverlap":50,"splitBy":"sentence"}
     */
    private String chunkConfig;
}
