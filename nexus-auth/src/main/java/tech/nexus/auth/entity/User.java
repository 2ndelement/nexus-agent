package tech.nexus.auth.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import lombok.experimental.Accessors;

import java.time.LocalDateTime;

/**
 * 用户实体（对应 `user` 表）。
 */
@Data
@Accessors(chain = true)
@TableName("`user`")
public class User {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 租户 ID */
    private Long tenantId;

    /** 用户名（租户内唯一） */
    private String username;

    /** 邮箱 */
    private String email;

    /** BCrypt 加密后的密码 */
    private String password;

    /** 角色列表，逗号分隔，如 "ADMIN,USER" */
    private String roles;

    /** 状态：1=正常，0=禁用 */
    private Integer status;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;
}
