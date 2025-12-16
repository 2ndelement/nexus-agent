package tech.nexus.agentconfig.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tech.nexus.agentconfig.dto.SkillRequest;
import tech.nexus.agentconfig.dto.SkillVO;
import tech.nexus.agentconfig.entity.AgentSkill;
import tech.nexus.agentconfig.entity.Skill;
import tech.nexus.agentconfig.mapper.AgentSkillMapper;
import tech.nexus.agentconfig.mapper.SkillMapper;
import tech.nexus.agentconfig.service.SkillService;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.ResultCode;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Skill 管理服务实现。
 *
 * <p>规范对标 /root/.agents/skills：
 * <ul>
 *   <li>每个 Skill 是一个目录：/tmp/nexus-skills/{name}/SKILL.md</li>
 *   <li>SKILL.md frontmatter 包含 name / description</li>
 *   <li>RAG 关键词匹配：在 description / keywords 字段中模糊检索</li>
 * </ul>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SkillServiceImpl implements SkillService {

    private final SkillMapper skillMapper;
    private final AgentSkillMapper agentSkillMapper;

    @Value("${nexus.skill.base-dir:/tmp/nexus-skills}")
    private String skillBaseDir;

    // ────────────────────────────────────────────────────────
    // CRUD
    // ────────────────────────────────────────────────────────

    @Override
    @Transactional(rollbackFor = Exception.class)
    public SkillVO create(SkillRequest request) {
        validateSkillName(request.getName());

        // 唯一性校验
        long count = skillMapper.selectCount(
                new LambdaQueryWrapper<Skill>().eq(Skill::getName, request.getName()));
        if (count > 0) {
            throw new BizException(ResultCode.PARAM_ERROR, "Skill 已存在：" + request.getName());
        }

        // 写本地文件
        String filePath = writeSkillFile(request.getName(), request.getContent());

        // 写 DB 元数据
        Skill skill = new Skill();
        skill.setName(request.getName());
        skill.setDescription(request.getDescription());
        skill.setFilePath(filePath);
        skill.setContent(request.getContent());
        skill.setKeywords(extractKeywords(request.getKeywords(), request.getDescription()));
        skill.setCreateTime(LocalDateTime.now());
        skill.setUpdateTime(LocalDateTime.now());
        skillMapper.insert(skill);

        log.info("Created skill[{}] at {}", skill.getName(), filePath);
        return toVO(skill);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public SkillVO update(String name, SkillRequest request) {
        Skill existing = fetchSkill(name);

        // 更新本地文件
        String filePath = writeSkillFile(name, request.getContent());

        existing.setDescription(request.getDescription());
        existing.setFilePath(filePath);
        existing.setContent(request.getContent());
        existing.setKeywords(extractKeywords(request.getKeywords(), request.getDescription()));
        existing.setUpdateTime(LocalDateTime.now());
        skillMapper.updateById(existing);

        log.info("Updated skill[{}]", name);
        return toVO(existing);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(String name) {
        Skill skill = fetchSkill(name);

        // 删除绑定关系
        agentSkillMapper.delete(
                new LambdaQueryWrapper<AgentSkill>().eq(AgentSkill::getSkillName, name));

        // 删除本地文件目录
        deleteSkillDir(name);

        skillMapper.deleteById(skill.getId());
        log.info("Deleted skill[{}]", name);
    }

    @Override
    public SkillVO getByName(String name) {
        return toVO(fetchSkill(name));
    }

    @Override
    public List<SkillVO> listAll() {
        return skillMapper.selectList(null).stream().map(this::toVO).collect(Collectors.toList());
    }

    /**
     * RAG 关键词检索。
     *
     * <p>简单实现：在 description 和 keywords 中做 LIKE 模糊匹配，
     * 匹配分数 = description 包含 query 的词数，倒序排列。
     */
    @Override
    public List<SkillVO> search(String query) {
        if (query == null || query.isBlank()) {
            return listAll();
        }
        String likePattern = "%" + query.trim() + "%";
        List<Skill> results = skillMapper.selectList(
                new LambdaQueryWrapper<Skill>()
                        .like(Skill::getDescription, query.trim())
                        .or()
                        .like(Skill::getKeywords, query.trim())
        );

        // 按描述匹配度粗排序（匹配词在前面的得分更高）
        String lowerQuery = query.toLowerCase();
        return results.stream()
                .sorted(Comparator.comparingInt((Skill s) ->
                        s.getDescription().toLowerCase().indexOf(lowerQuery)).reversed()
                        .thenComparing(Skill::getName))
                .map(this::toVO)
                .collect(Collectors.toList());
    }

    // ────────────────────────────────────────────────────────
    // Agent 绑定
    // ────────────────────────────────────────────────────────

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void bindToAgent(Long agentId, String skillName) {
        fetchSkill(skillName); // 验证 skill 存在

        long count = agentSkillMapper.selectCount(
                new LambdaQueryWrapper<AgentSkill>()
                        .eq(AgentSkill::getAgentId, agentId)
                        .eq(AgentSkill::getSkillName, skillName));
        if (count > 0) {
            throw new BizException(ResultCode.PARAM_ERROR, "Skill 已绑定到该 Agent");
        }

        AgentSkill binding = new AgentSkill();
        binding.setAgentId(agentId);
        binding.setSkillName(skillName);
        binding.setCreateTime(LocalDateTime.now());
        agentSkillMapper.insert(binding);
        log.info("Bound skill[{}] to agent[{}]", skillName, agentId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void unbindFromAgent(Long agentId, String skillName) {
        agentSkillMapper.delete(
                new LambdaQueryWrapper<AgentSkill>()
                        .eq(AgentSkill::getAgentId, agentId)
                        .eq(AgentSkill::getSkillName, skillName));
        log.info("Unbound skill[{}] from agent[{}]", skillName, agentId);
    }

    @Override
    public List<SkillVO> listByAgent(Long agentId) {
        List<AgentSkill> bindings = agentSkillMapper.selectList(
                new LambdaQueryWrapper<AgentSkill>().eq(AgentSkill::getAgentId, agentId));

        if (bindings.isEmpty()) {
            return List.of();
        }

        List<String> skillNames = bindings.stream()
                .map(AgentSkill::getSkillName)
                .collect(Collectors.toList());

        return skillMapper.selectList(
                        new LambdaQueryWrapper<Skill>().in(Skill::getName, skillNames))
                .stream()
                .map(this::toVO)
                .collect(Collectors.toList());
    }

    // ────────────────────────────────────────────────────────
    // Private Helpers
    // ────────────────────────────────────────────────────────

    private Skill fetchSkill(String name) {
        Skill skill = skillMapper.selectOne(
                new LambdaQueryWrapper<Skill>().eq(Skill::getName, name));
        if (skill == null) {
            throw new BizException(ResultCode.NOT_FOUND, "Skill 不存在：" + name);
        }
        return skill;
    }

    /**
     * 校验 Skill 名称格式：只允许字母、数字、中划线、下划线。
     */
    private void validateSkillName(String name) {
        if (!name.matches("[a-zA-Z0-9_-]+")) {
            throw new BizException(ResultCode.PARAM_ERROR,
                    "Skill 名称只允许字母、数字、中划线、下划线：" + name);
        }
    }

    /**
     * 写 SKILL.md 到本地文件系统。
     *
     * @return 文件绝对路径
     */
    private String writeSkillFile(String name, String content) {
        Path dir = Paths.get(skillBaseDir, name);
        Path file = dir.resolve("SKILL.md");
        try {
            Files.createDirectories(dir);
            Files.writeString(file, content, StandardCharsets.UTF_8);
            return file.toAbsolutePath().toString();
        } catch (IOException e) {
            throw new BizException(ResultCode.INTERNAL_ERROR,
                    "写 SKILL.md 文件失败：" + e.getMessage());
        }
    }

    /**
     * 删除 Skill 目录（递归）。
     */
    private void deleteSkillDir(String name) {
        Path dir = Paths.get(skillBaseDir, name);
        try {
            if (Files.exists(dir)) {
                Files.walk(dir)
                        .sorted(Comparator.reverseOrder())
                        .map(Path::toFile)
                        .forEach(File::delete);
            }
        } catch (IOException e) {
            log.warn("Failed to delete skill dir: {}", dir, e);
        }
    }

    /**
     * 提取关键词：优先使用用户提供的，否则从 description 提取（按空格分词，取前 10 词）。
     */
    private String extractKeywords(String userKeywords, String description) {
        if (userKeywords != null && !userKeywords.isBlank()) {
            return userKeywords.trim();
        }
        if (description == null || description.isBlank()) {
            return "";
        }
        // 简单分词：按空格、逗号、中文标点切分
        String[] words = description.split("[\\s,，。！？.!?]+");
        return Arrays.stream(words)
                .filter(w -> w.length() >= 2)
                .limit(10)
                .collect(Collectors.joining(","));
    }

    private SkillVO toVO(Skill skill) {
        SkillVO vo = new SkillVO();
        vo.setId(skill.getId());
        vo.setName(skill.getName());
        vo.setDescription(skill.getDescription());
        vo.setFilePath(skill.getFilePath());
        vo.setKeywords(skill.getKeywords());
        vo.setContent(skill.getContent());
        vo.setCreateTime(skill.getCreateTime());
        vo.setUpdateTime(skill.getUpdateTime());
        return vo;
    }
}
