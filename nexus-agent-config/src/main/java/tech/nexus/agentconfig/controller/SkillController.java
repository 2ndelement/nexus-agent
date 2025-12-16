package tech.nexus.agentconfig.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import tech.nexus.agentconfig.dto.SkillRequest;
import tech.nexus.agentconfig.dto.SkillVO;
import tech.nexus.agentconfig.service.SkillService;
import tech.nexus.common.result.Result;

import java.util.List;

/**
 * Skill 管理 Controller。
 */
@RestController
@RequestMapping("/api/agent-config/skills")
@RequiredArgsConstructor
public class SkillController {

    private final SkillService skillService;

    /** 创建 Skill */
    @PostMapping
    public Result<SkillVO> create(@Valid @RequestBody SkillRequest request) {
        return Result.success(skillService.create(request));
    }

    /** 列出所有 Skill */
    @GetMapping
    public Result<List<SkillVO>> listAll() {
        return Result.success(skillService.listAll());
    }

    /** RAG 关键词检索 */
    @GetMapping("/search")
    public Result<List<SkillVO>> search(@RequestParam String query) {
        return Result.success(skillService.search(query));
    }

    /** 查询 Skill 详情 */
    @GetMapping("/{name}")
    public Result<SkillVO> getByName(@PathVariable String name) {
        return Result.success(skillService.getByName(name));
    }

    /** 更新 Skill */
    @PutMapping("/{name}")
    public Result<SkillVO> update(
            @PathVariable String name,
            @Valid @RequestBody SkillRequest request) {
        return Result.success(skillService.update(name, request));
    }

    /** 删除 Skill */
    @DeleteMapping("/{name}")
    public Result<Void> delete(@PathVariable String name) {
        skillService.delete(name);
        return Result.success();
    }

    // ── Agent 绑定 ────────────────────────────────────────────

    /** 将 Skill 绑定到 Agent */
    @PostMapping("/bind/{agentId}/{skillName}")
    public Result<Void> bindToAgent(
            @PathVariable Long agentId,
            @PathVariable String skillName) {
        skillService.bindToAgent(agentId, skillName);
        return Result.success();
    }

    /** 解绑 */
    @DeleteMapping("/bind/{agentId}/{skillName}")
    public Result<Void> unbindFromAgent(
            @PathVariable Long agentId,
            @PathVariable String skillName) {
        skillService.unbindFromAgent(agentId, skillName);
        return Result.success();
    }

    /** 查询 Agent 绑定的 Skill 列表 */
    @GetMapping("/agent/{agentId}")
    public Result<List<SkillVO>> listByAgent(@PathVariable Long agentId) {
        return Result.success(skillService.listByAgent(agentId));
    }
}
