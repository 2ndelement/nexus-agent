package tech.nexus.knowledge.dto;

import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 文档 VO（视图对象）。
 */
@Data
@Builder
public class DocumentVO {

    private Long id;
    private Long tenantId;
    private Long kbId;
    private String name;
    private Long fileSize;
    private String fileType;
    private String parseStatus;
    private Integer chunkCount;
    private String errorMsg;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
