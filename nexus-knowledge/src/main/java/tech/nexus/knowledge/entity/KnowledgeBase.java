package tech.nexus.knowledge.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 知识库实体。
 *
 * <p>多租户隔离核心字段：tenant_id。
 * 同一租户内知识库名称唯一（uk_tenant_name）。
 */
@Data
@TableName("knowledge_base")
public class KnowledgeBase {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 租户ID，多租户隔离核心字段 */
    private Long tenantId;

    /** 知识库名称（租户内唯一） */
    private String name;

    /** 知识库描述 */
    private String description;

    /**
     * 知识库类型：
     * GENERAL=通用  QA=问答对  CODE=代码
     */
    private String type;

    /**
     * 使用的 Embedding 模型，默认 sentence-transformers
     */
    private String embedModel;

    /**
     * 分片策略（JSON 字符串），包含 chunkSize/chunkOverlap/splitBy 等配置。
     * 示例：{"chunkSize":500,"chunkOverlap":50,"splitBy":"sentence"}
     */
    private String chunkConfig;

    /**
     * 状态：1=正常 2=构建中 0=禁用
     */
    private Integer status;

    /** 文档数量 */
    private Integer docCount;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;
}
