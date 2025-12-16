package tech.nexus.agentconfig.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * Skill 元数据实体。
 *
 * <p>对标 /root/.agents/skills 中每个 skill 目录下的 SKILL.md：
 * <ul>
 *   <li>frontmatter: name / description</li>
 *   <li>body: Markdown 正文（即文件内容）</li>
 * </ul>
 * 文件本体存储于 /tmp/nexus-skills/{name}/SKILL.md，数据库存元数据及关键词索引。
 */
@Data
@TableName("skill")
public class Skill implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.AUTO)
    private Long id;

    /** Skill 唯一名称（对应目录名） */
    private String name;

    /** 用于 RAG 关键词匹配的 description（SKILL.md frontmatter） */
    private String description;

    /** 本地文件存储路径（/tmp/nexus-skills/{name}/SKILL.md） */
    private String filePath;

    /** SKILL.md 完整内容（冗余存储，便于关键词检索） */
    private String content;

    /** RAG 关键词，逗号分隔，从 description 提取 */
    private String keywords;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;
}
