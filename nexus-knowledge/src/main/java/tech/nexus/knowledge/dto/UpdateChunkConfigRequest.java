package tech.nexus.knowledge.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

/**
 * 更新文档分片配置请求 DTO。
 */
@Data
public class UpdateChunkConfigRequest {

    /** 分片大小（字符数），建议 200-1000 */
    @NotNull(message = "chunkSize 不能为空")
    private Integer chunkSize;

    /** 相邻分片重叠字符数，建议 0-200 */
    private Integer chunkOverlap;

    /**
     * 分片方式：sentence（按句子）/ paragraph（按段落）/ fixed（固定长度）
     */
    private String splitBy;
}
