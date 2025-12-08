package tech.nexus.billing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 每日用量记录实体
 */
@Data
@TableName("usage_daily")
public class UsageDaily {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 租户 ID */
    private Long tenantId;

    /** 统计日期 */
    private LocalDate statDate;

    /** API 调用次数 */
    private Integer apiCalls;

    /** 输入 Token 数 */
    private Long inputTokens;

    /** 输出 Token 数 */
    private Long outputTokens;

    /** 模型名称 */
    private String model;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;
}
