package tech.nexus.auth.dto;

import lombok.Builder;
import lombok.Data;

import java.util.List;

/**
 * 当前登录用户信息响应 DTO（/me 接口）。
 */
@Data
@Builder
public class UserInfoResponse {

    private Long userId;

    private Long tenantId;

    private String username;

    private String email;

    private List<String> roles;
}
