package tech.nexus.agentconfig.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import tech.nexus.agentconfig.dto.AgentConfigRequest;
import tech.nexus.agentconfig.dto.AgentConfigVO;
import tech.nexus.agentconfig.entity.AgentConfigHistory;
import tech.nexus.agentconfig.entity.ToolRegistry;
import tech.nexus.agentconfig.service.AgentConfigService;
import tech.nexus.agentconfig.service.ToolRegistryService;
import tech.nexus.common.result.Result;

import java.util.List;

/**
 * Agent 配置管理 Controller。
 *
 * <p>租户 ID 通过请求头 X-Tenant-Id 传入（简化鉴权，生产中应从 JWT 解析）。
 */
@RestController
@RequestMapping("/api/agent-config")
@RequiredArgsConstructor
public class AgentConfigController {

    private final AgentConfigService agentConfigService;
    private final ToolRegistryService toolRegistryService;

    // ── Agent CRUD ───────────────────────────────────────────

    @PostMapping("/agents")
    public Result<AgentConfigVO> create(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @Valid @RequestBody AgentConfigRequest request) {
        return Result.success(agentConfigService.create(tenantId, request));
    }

    @GetMapping("/agents")
    public Result<Page<AgentConfigVO>> list(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestParam(required = false) String name,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return Result.success(agentConfigService.list(tenantId, name, page, size));
    }

    @GetMapping("/agents/{id}")
    public Result<AgentConfigVO> getById(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @PathVariable Long id) {
        return Result.success(agentConfigService.getById(tenantId, id));
    }

    @PutMapping("/agents/{id}")
    public Result<AgentConfigVO> update(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @PathVariable Long id,
            @Valid @RequestBody AgentConfigRequest request) {
        return Result.success(agentConfigService.update(tenantId, id, request));
    }

    @DeleteMapping("/agents/{id}")
    public Result<Void> delete(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @PathVariable Long id) {
        agentConfigService.delete(tenantId, id);
        return Result.success();
    }

    // ── 版本管理 ─────────────────────────────────────────────

    @GetMapping("/agents/{id}/history")
    public Result<List<AgentConfigHistory>> listHistory(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @PathVariable Long id) {
        return Result.success(agentConfigService.listHistory(tenantId, id));
    }

    @PostMapping("/agents/{id}/rollback/{ver}")
    public Result<AgentConfigVO> rollback(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @PathVariable Long id,
            @PathVariable int ver) {
        return Result.success(agentConfigService.rollback(tenantId, id, ver));
    }

    // ── 工具注册表 ───────────────────────────────────────────

    @GetMapping("/tools")
    public Result<List<ToolRegistry>> listTools() {
        return Result.success(toolRegistryService.listAll());
    }

    // ── 模板 ─────────────────────────────────────────────────

    @GetMapping("/templates")
    public Result<List<AgentConfigVO>> listTemplates() {
        return Result.success(agentConfigService.listTemplates());
    }

    @PostMapping("/templates/{id}/fork")
    public Result<AgentConfigVO> forkTemplate(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @PathVariable Long id) {
        return Result.success(agentConfigService.forkTemplate(tenantId, id));
    }
}
