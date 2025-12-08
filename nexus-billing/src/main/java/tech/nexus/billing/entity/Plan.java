package tech.nexus.billing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 套餐定义实体
 */
@Data
@TableName("plan")
public class Plan {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 套餐名称 FREE / PRO / ENTERPRISE */
    private String name;

    /** 显示名称 */
    private String displayName;

    /** 最大用户数 */
    private Integer maxUsers;

    /** 最大 Agent 数 */
    private Integer maxAgents;

    /** 每日 API 调用上限 */
    private Integer maxApiCallsDay;

    /** 每日 Token 上限 */
    private Long maxTokensDay;

    /** 知识库容量上限（MB） */
    private Integer maxKbSizeMb;

    /** 月价格 */
    private BigDecimal priceMonthly;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
}
