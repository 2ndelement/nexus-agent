package tech.nexus.auth.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import lombok.experimental.Accessors;

import java.time.LocalDateTime;

/**
 * 组织成员实体（对应 `organization_user` 表）。
 *
 * <p>V5 新增：用户-组织多对多关联。
 */
@Data
@Accessors(chain = true)
@TableName("organization_user")
public class OrganizationUser {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 组织 ID */
    private Long organizationId;

    /** 用户 ID */
    private Long userId;

    /** 角色: OWNER / ADMIN / MEMBER */
    private String role;

    /** 状态：1=正常 0=已离开 */
    private Integer status;

    /** 加入时间 */
    private LocalDateTime joinedAt;

    /** 邀请人 ID */
    private Long invitedBy;
}
