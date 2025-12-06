package tech.nexus.tenant.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import tech.nexus.common.result.Result;
import tech.nexus.tenant.dto.*;
import tech.nexus.tenant.service.TenantService;

import java.util.List;

/**
 * 租户管理控制器
 *
 * <pre>
 * POST   /api/tenant/                   创建租户
 * GET    /api/tenant/{id}               查询租户
 * PUT    /api/tenant/{id}               更新租户
 * POST   /api/tenant/{id}/members       添加成员
 * DELETE /api/tenant/{id}/members/{uid} 移除成员
 * GET    /api/tenant/{id}/members       成员列表
 * </pre>
 */
@RestController
@RequestMapping("/api/tenant")
@RequiredArgsConstructor
public class TenantController {

    private final TenantService tenantService;

    /** 创建租户（系统管理员用） */
    @PostMapping("/")
    public Result<TenantVO> createTenant(@Valid @RequestBody CreateTenantRequest req) {
        return Result.success(tenantService.createTenant(req));
    }

    /** 查询租户信息 */
    @GetMapping("/{id}")
    public Result<TenantVO> getTenant(@PathVariable Long id) {
        return Result.success(tenantService.getTenant(id));
    }

    /** 更新租户配置 */
    @PutMapping("/{id}")
    public Result<TenantVO> updateTenant(@PathVariable Long id,
                                         @RequestBody UpdateTenantRequest req) {
        return Result.success(tenantService.updateTenant(id, req));
    }

    /** 添加成员（幂等） */
    @PostMapping("/{id}/members")
    public Result<MemberVO> addMember(@PathVariable Long id,
                                      @Valid @RequestBody AddMemberRequest req) {
        return Result.success(tenantService.addMember(id, req));
    }

    /** 移除成员（软删除） */
    @DeleteMapping("/{id}/members/{uid}")
    public Result<Void> removeMember(@PathVariable Long id,
                                     @PathVariable Long uid) {
        tenantService.removeMember(id, uid);
        return Result.success();
    }

    /** 成员列表 */
    @GetMapping("/{id}/members")
    public Result<List<MemberVO>> listMembers(@PathVariable Long id) {
        return Result.success(tenantService.listMembers(id));
    }
}
