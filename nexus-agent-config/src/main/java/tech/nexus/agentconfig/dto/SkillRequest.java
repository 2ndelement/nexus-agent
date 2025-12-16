package tech.nexus.agentconfig.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 创建/更新 Skill 请求 DTO。
 */
@Data
public class SkillRequest {

    /** Skill 唯一名称（对应目录名，仅含字母数字中划线） */
    @NotBlank(message = "skill name 不能为空")
    @Size(max = 100)
    private String name;

    /** 用于 RAG 匹配的 description（SKILL.md frontmatter） */
    @NotBlank(message = "skill description 不能为空")
    private String description;

    /**
     * SKILL.md 完整内容（含 frontmatter 和 body）。
     * 格式：
     * <pre>
     * ---
     * name: xxx
     * description: yyy
     * ---
     * # Title
     * ...
     * </pre>
     */
    @NotBlank(message = "SKILL.md 内容不能为空")
    private String content;

    /** RAG 关键词（逗号分隔，可选；为空时由 description 自动提取） */
    private String keywords;
}
