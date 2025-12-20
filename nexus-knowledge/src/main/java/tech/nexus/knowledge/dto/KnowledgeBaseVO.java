package tech.nexus.knowledge.dto;

import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 知识库 VO（视图对象），返回给前端。
 */
@Data
@Builder
public class KnowledgeBaseVO {

    private Long id;
    private Long tenantId;
    private String name;
    private String description;
    private String type;
    private String embedModel;
    private String chunkConfig;
    private Integer status;
    private Integer docCount;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
