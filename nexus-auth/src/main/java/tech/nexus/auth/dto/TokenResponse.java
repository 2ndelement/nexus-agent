package tech.nexus.auth.dto;

import lombok.Builder;
import lombok.Data;

import java.util.List;

/**
 * Token 响应 DTO。
 *
 * <p>V5 重构：登录/注册后返回用户信息和组织列表。
 */
@Data
@Builder
public class TokenResponse {

    private String accessToken;

    private String refreshToken;

    /** Access Token 有效期（秒） */
    private long expiresIn;

    @Builder.Default
    private String tokenType = "Bearer";

    /** 用户信息 */
    private UserInfo user;

    /** 用户加入的组织列表（含角色） */
    private List<OrganizationWithRole> organizations;

    /**
     * 用户基本信息
     */
    @Data
    @Builder
    public static class UserInfo {
        private Long id;
        private String username;
        private String email;
        private String nickname;
        private String avatar;
        private Integer personalAgentLimit;
        private Integer orgCreateLimit;
        private Integer orgJoinLimit;
    }

    /**
     * 用户所属组织（含角色）
     */
    @Data
    @Builder
    public static class OrganizationWithRole {
        private Long id;
        private String code;
        private String name;
        private String avatar;
        /** 当前用户在此组织的角色: OWNER / ADMIN / MEMBER */
        private String role;
    }
}
