package tech.nexus.auth.dto;

import lombok.Builder;
import lombok.Data;

import java.util.List;

/**
 * 当前登录用户信息响应 DTO（/me 接口）。
 *
 * <p>V5 重构：移除 tenantId，添加组织列表和配额信息。
 */
@Data
@Builder
public class UserInfoResponse {

    private Long userId;

    private String username;

    private String email;

    private String nickname;

    private String avatar;

    private List<String> roles;

    /** 个人 Agent 数量上限 */
    private Integer personalAgentLimit;

    /** 可创建组织数量上限 */
    private Integer orgCreateLimit;

    /** 可加入组织数量上限 */
    private Integer orgJoinLimit;

    /** 用户加入的组织列表 */
    private List<TokenResponse.OrganizationWithRole> organizations;
}
