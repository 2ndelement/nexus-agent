package tech.nexus.billing.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 租户配额实体
 */
@Data
@TableName("tenant_quota")
public class TenantQuota {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 租户 ID */
    private Long tenantId;

    /** 绑定套餐 ID */
    private Long planId;

    /** 额外购买的调用次数 */
    private Integer extraCalls;

    /** 额外购买的 Token 数 */
    private Long extraTokens;

    /** 套餐到期日，null = 永久有效 */
    private LocalDate validUntil;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;
}
