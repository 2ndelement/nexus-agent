package tech.nexus.agentconfig.service;

import tech.nexus.agentconfig.dto.SkillRequest;
import tech.nexus.agentconfig.dto.SkillVO;

import java.util.List;

/**
 * Skill 管理服务接口。
 *
 * <p>对标 /root/.agents/skills 规范（SKILL.md 格式）：
 * <ul>
 *   <li>MySQL 存元数据（name / description / filePath / keywords）</li>
 *   <li>文件存本地 /tmp/nexus-skills/{name}/SKILL.md</li>
 *   <li>RAG 关键词匹配 description 字段</li>
 * </ul>
 */
public interface SkillService {

    /** 创建 Skill（写 DB 元数据 + 写本地文件） */
    SkillVO create(SkillRequest request);

    /** 更新 Skill */
    SkillVO update(String name, SkillRequest request);

    /** 删除 Skill（删 DB + 删本地文件） */
    void delete(String name);

    /** 查询 Skill 详情 */
    SkillVO getByName(String name);

    /** 列出所有 Skill */
    List<SkillVO> listAll();

    /**
     * RAG 关键词检索：在 description / keywords 中模糊匹配 query。
     *
     * @param query 用户输入的查询词
     * @return 匹配的 Skill 列表（按匹配度排序）
     */
    List<SkillVO> search(String query);

    /** 绑定 Skill 到 Agent */
    void bindToAgent(Long agentId, String skillName);

    /** 解绑 Skill */
    void unbindFromAgent(Long agentId, String skillName);

    /** 查询 Agent 已绑定的 Skill 列表 */
    List<SkillVO> listByAgent(Long agentId);
}
