package tech.nexus.knowledge.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import tech.nexus.common.result.PageResult;
import tech.nexus.common.result.Result;
import tech.nexus.knowledge.dto.*;
import tech.nexus.knowledge.service.impl.KnowledgeBaseServiceImpl;

import java.util.List;

/**
 * 知识库管理控制器。
 *
 * <pre>
 * POST   /api/knowledge/bases                           创建知识库
 * GET    /api/knowledge/bases                           列出知识库（分页）
 * GET    /api/knowledge/bases/{id}                      获取知识库详情
 * PUT    /api/knowledge/bases/{id}                      更新知识库
 * DELETE /api/knowledge/bases/{id}                      删除知识库
 * PUT    /api/knowledge/bases/{id}/chunk-config          更新分片配置
 *
 * POST   /api/knowledge/bases/{id}/permissions           授予权限
 * DELETE /api/knowledge/bases/{id}/permissions/{userId}  撤销权限
 * GET    /api/knowledge/bases/{id}/permissions           列出权限
 *
 * POST   /api/knowledge/bases/{id}/bind/{agentId}        绑定 Agent
 * DELETE /api/knowledge/bases/{id}/bind/{agentId}        解绑 Agent
 * </pre>
 *
 * <p>多租户隔离：tenantId 和 userId 从请求头 X-Tenant-Id / X-User-Id 获取。
 * 在生产环境中，这两个 Header 由 Gateway 解析 JWT 后注入，下游服务直接信任。
 */
@RestController
@RequestMapping("/api/knowledge/bases")
@RequiredArgsConstructor
public class KnowledgeBaseController {

    private final KnowledgeBaseServiceImpl kbService;

    // ─── 知识库 CRUD ──────────────────────────────────────────────────────────

    /** 创建知识库，自动为当前用户授予 OWNER 权限 */
    @PostMapping
    public Result<KnowledgeBaseVO> create(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @Valid @RequestBody CreateKbRequest req) {
        return Result.success(kbService.create(tenantId, userId, req));
    }

    /** 列出当前用户有权限的知识库（分页） */
    @GetMapping
    public Result<PageResult<KnowledgeBaseVO>> list(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        return Result.success(kbService.list(tenantId, userId, page, size));
    }

    /** 获取知识库详情 */
    @GetMapping("/{id}")
    public Result<KnowledgeBaseVO> get(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @PathVariable Long id) {
        return Result.success(kbService.getById(tenantId, id));
    }

    /** 更新知识库基本信息（需要 EDITOR 及以上权限） */
    @PutMapping("/{id}")
    public Result<KnowledgeBaseVO> update(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long id,
            @RequestBody UpdateKbRequest req) {
        return Result.success(kbService.update(tenantId, userId, id, req));
    }

    /** 删除知识库（需要 OWNER 权限） */
    @DeleteMapping("/{id}")
    public Result<Void> delete(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long id) {
        kbService.delete(tenantId, userId, id);
        return Result.success();
    }

    /** 更新分片配置（需要 EDITOR 及以上权限） */
    @PutMapping("/{id}/chunk-config")
    public Result<KnowledgeBaseVO> updateChunkConfig(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long id,
            @Valid @RequestBody UpdateChunkConfigRequest req) {
        return Result.success(kbService.updateChunkConfig(tenantId, userId, id, req));
    }

    // ─── 权限管理 ─────────────────────────────────────────────────────────────

    /** 授予用户知识库权限（需要 OWNER 权限，幂等） */
    @PostMapping("/{id}/permissions")
    public Result<KbPermissionVO> grantPermission(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long id,
            @Valid @RequestBody GrantPermissionRequest req) {
        return Result.success(kbService.grantPermission(tenantId, userId, id, req));
    }

    /** 撤销用户知识库权限（需要 OWNER 权限） */
    @DeleteMapping("/{id}/permissions/{targetUserId}")
    public Result<Void> revokePermission(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long id,
            @PathVariable Long targetUserId) {
        kbService.revokePermission(tenantId, userId, id, targetUserId);
        return Result.success();
    }

    /** 列出知识库权限（需要 VIEWER 及以上权限） */
    @GetMapping("/{id}/permissions")
    public Result<List<KbPermissionVO>> listPermissions(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long id) {
        return Result.success(kbService.listPermissions(tenantId, userId, id));
    }

    // ─── Agent 绑定 ───────────────────────────────────────────────────────────

    /** 绑定知识库到 Agent（幂等） */
    @PostMapping("/{id}/bind/{agentId}")
    public Result<Void> bindAgent(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @PathVariable Long id,
            @PathVariable Long agentId) {
        kbService.bindAgent(tenantId, id, agentId);
        return Result.success();
    }

    /** 解绑知识库与 Agent */
    @DeleteMapping("/{id}/bind/{agentId}")
    public Result<Void> unbindAgent(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @PathVariable Long id,
            @PathVariable Long agentId) {
        kbService.unbindAgent(tenantId, id, agentId);
        return Result.success();
    }
}
