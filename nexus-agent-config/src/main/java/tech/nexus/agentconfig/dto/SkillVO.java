package tech.nexus.agentconfig.dto;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * Skill 响应 VO。
 */
@Data
public class SkillVO {

    private Long id;
    private String name;
    private String description;
    private String filePath;
    private String keywords;
    private String content;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
