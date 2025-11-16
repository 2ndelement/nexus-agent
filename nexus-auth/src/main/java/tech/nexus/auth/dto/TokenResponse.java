package tech.nexus.auth.dto;

import lombok.Builder;
import lombok.Data;

/**
 * Token 响应 DTO。
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
}
