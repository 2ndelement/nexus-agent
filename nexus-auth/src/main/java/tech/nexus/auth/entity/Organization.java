package tech.nexus.auth.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import lombok.experimental.Accessors;

import java.time.LocalDateTime;

/**
 * 组织实体（对应 `organization` 表）。
 *
 * <p>V5 新增：替代旧的 tenant 概念。
 */
@Data
@Accessors(chain = true)
@TableName("organization")
public class Organization {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 组织代码（URL友好，全局唯一） */
    private String code;

    /** 组织名称 */
    private String name;

    /** 组织描述 */
    private String description;

    /** 组织头像 URL */
    private String avatar;

    /** 创建者 ID（OWNER） */
    private Long ownerId;

    /** 套餐：FREE/PRO/ENTERPRISE */
    private String plan;

    /** 状态：1=正常 0=禁用 */
    private Integer status;

    /** 成员数量上限 */
    private Integer memberLimit;

    /** Agent 数量上限 */
    private Integer agentLimit;

    private LocalDateTime createdAt;

    private LocalDateTime updatedAt;
}
