package tech.nexus.knowledge.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 文档实体。
 *
 * <p>parse_status 生命周期：PENDING → PARSING → DONE / FAILED
 */
@Data
@TableName("document")
public class Document {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 租户ID */
    private Long tenantId;

    /** 所属知识库ID */
    private Long kbId;

    /** 文件名 */
    private String name;

    /** 文件存储路径（本地 /data/uploads/{tenantId}/{docId}/ 或 MinIO） */
    private String filePath;

    /** 文件大小（字节） */
    private Long fileSize;

    /** 文件类型：pdf/txt/md/docx */
    private String fileType;

    /**
     * 解析状态：PENDING / PARSING / DONE / FAILED
     */
    private String parseStatus;

    /** 切片数量（向量化完成后更新） */
    private Integer chunkCount;

    /** 解析失败时的错误信息 */
    private String errorMsg;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;
}
