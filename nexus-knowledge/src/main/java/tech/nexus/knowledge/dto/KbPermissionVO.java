package tech.nexus.knowledge.dto;

import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 知识库权限 VO。
 */
@Data
@Builder
public class KbPermissionVO {

    private Long id;
    private Long kbId;
    private Long userId;
    private String role;
    private LocalDateTime createTime;
}
