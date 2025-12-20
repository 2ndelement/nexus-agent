package tech.nexus.knowledge.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 文档分片实体。
 *
 * <p>每个文档上传后，内容会按 chunkSize/chunkOverlap 分片存储到本表，
 * 供向量化服务和检索使用。
 */
@Data
@TableName("document_chunk")
public class DocumentChunk {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 所属文档 ID */
    private Long docId;

    /** 所属知识库 ID */
    private Long kbId;

    /** 租户 ID */
    private Long tenantId;

    /** 分片序号（从 0 开始） */
    private Integer chunkIndex;

    /** 分片内容文本 */
    private String content;

    /** 分片字符数 */
    private Integer charCount;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
}
