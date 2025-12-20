package tech.nexus.knowledge.dto;

import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 更新知识库请求 DTO。
 */
@Data
public class UpdateKbRequest {

    @Size(max = 100, message = "知识库名称最多100字符")
    private String name;

    @Size(max = 500, message = "描述最多500字符")
    private String description;

    /** 知识库类型 */
    private String type;

    /** Embedding 模型 */
    private String embedModel;

    /** 分片策略配置（JSON 字符串） */
    private String chunkConfig;
}
