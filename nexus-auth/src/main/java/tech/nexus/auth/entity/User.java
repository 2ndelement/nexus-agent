package tech.nexus.auth.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import lombok.experimental.Accessors;

import java.time.LocalDateTime;

/**
 * 用户实体（对应 `user` 表）。
 *
 * <p>V5 重构：用户不再绑定 tenantId，改为独立注册。
 * 用户可创建/加入多个组织 (Organization)，通过 organization_user 表关联。
 */
@Data
@Accessors(chain = true)
@TableName("`user`")
public class User {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 用户名（全局唯一） */
    private String username;

    /** 邮箱（可选，全局唯一） */
    private String email;

    /** 手机号（可选） */
    private String phone;

    /** BCrypt 加密后的密码 */
    private String password;

    /** 昵称 */
    private String nickname;

    /** 头像 URL */
    private String avatar;

    /** 角色列表，逗号分隔，如 "ADMIN,USER" */
    private String roles;

    /** 状态：1=正常，0=禁用 */
    private Integer status;

    /** 个人 Agent 数量上限 */
    private Integer personalAgentLimit;

    /** 可创建组织数量上限 */
    private Integer orgCreateLimit;

    /** 可加入组织数量上限 */
    private Integer orgJoinLimit;

    private LocalDateTime createdAt;

    private LocalDateTime updatedAt;
}
