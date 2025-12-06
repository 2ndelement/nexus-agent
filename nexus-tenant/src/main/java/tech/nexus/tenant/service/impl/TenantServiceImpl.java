package tech.nexus.tenant.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.ResultCode;
import tech.nexus.tenant.dto.*;
import tech.nexus.tenant.entity.Tenant;
import tech.nexus.tenant.entity.TenantUser;
import tech.nexus.tenant.mapper.TenantMapper;
import tech.nexus.tenant.mapper.TenantUserMapper;
import tech.nexus.tenant.service.TenantService;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 租户服务实现
 *
 * <p>所有成员操作强制携带 tenantId 隔离，杜绝跨租户访问。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TenantServiceImpl implements TenantService {

    private final TenantMapper tenantMapper;
    private final TenantUserMapper tenantUserMapper;

    // ─────────────────────────── 租户 CRUD ───────────────────────────

    @Override
    @Transactional
    public TenantVO createTenant(CreateTenantRequest req) {
        Tenant tenant = new Tenant();
        tenant.setName(req.getName());
        tenant.setPlan(req.getPlan() != null ? req.getPlan() : "FREE");
        tenant.setStatus(1);
        tenant.setCreateTime(LocalDateTime.now());
        tenant.setUpdateTime(LocalDateTime.now());
        tenantMapper.insert(tenant);
        log.info("创建租户: id={}, name={}", tenant.getId(), tenant.getName());
        return toVO(tenant);
    }

    @Override
    public TenantVO getTenant(Long id) {
        Tenant tenant = tenantMapper.selectById(id);
        if (tenant == null) {
            throw new BizException(ResultCode.TENANT_NOT_FOUND);
        }
        return toVO(tenant);
    }

    @Override
    @Transactional
    public TenantVO updateTenant(Long id, UpdateTenantRequest req) {
        Tenant tenant = tenantMapper.selectById(id);
        if (tenant == null) {
            throw new BizException(ResultCode.TENANT_NOT_FOUND);
        }
        if (req.getName() != null && !req.getName().isBlank()) {
            tenant.setName(req.getName());
        }
        if (req.getPlan() != null) {
            tenant.setPlan(req.getPlan());
        }
        if (req.getStatus() != null) {
            tenant.setStatus(req.getStatus());
        }
        tenant.setUpdateTime(LocalDateTime.now());
        tenantMapper.updateById(tenant);
        return toVO(tenant);
    }

    // ─────────────────────────── 成员管理 ───────────────────────────

    @Override
    @Transactional
    public MemberVO addMember(Long tenantId, AddMemberRequest req) {
        // 校验租户存在
        Tenant tenant = tenantMapper.selectById(tenantId);
        if (tenant == null) {
            throw new BizException(ResultCode.TENANT_NOT_FOUND);
        }

        String role = req.getRole() != null ? req.getRole() : "MEMBER";

        // 幂等处理：查询是否已存在（含软删除记录）
        TenantUser existing = tenantUserMapper.selectOne(
                new LambdaQueryWrapper<TenantUser>()
                        .eq(TenantUser::getTenantId, tenantId)
                        .eq(TenantUser::getUserId, req.getUserId())
        );

        if (existing != null) {
            // 已存在：更新 role 和 status（重新激活软删成员）
            existing.setRole(role);
            existing.setStatus(1);
            tenantUserMapper.updateById(existing);
            log.info("成员已存在，更新: tenantId={}, userId={}, role={}", tenantId, req.getUserId(), role);
            return toMemberVO(existing);
        }

        // 不存在：新增
        TenantUser tu = new TenantUser();
        tu.setTenantId(tenantId);
        tu.setUserId(req.getUserId());
        tu.setRole(role);
        tu.setStatus(1);
        tu.setCreateTime(LocalDateTime.now());
        tenantUserMapper.insert(tu);
        log.info("添加成员: tenantId={}, userId={}, role={}", tenantId, req.getUserId(), role);
        return toMemberVO(tu);
    }

    @Override
    @Transactional
    public void removeMember(Long tenantId, Long userId) {
        // 强制带 tenantId 隔离，防止跨租户操作
        int rows = tenantUserMapper.update(null,
                new LambdaUpdateWrapper<TenantUser>()
                        .eq(TenantUser::getTenantId, tenantId)
                        .eq(TenantUser::getUserId, userId)
                        .set(TenantUser::getStatus, 0)
        );
        if (rows == 0) {
            throw new BizException(ResultCode.NOT_FOUND, "成员不存在或已移除");
        }
        log.info("移除成员: tenantId={}, userId={}", tenantId, userId);
    }

    @Override
    public List<MemberVO> listMembers(Long tenantId) {
        // 强制带 tenantId 过滤，只返回当前租户的有效成员
        List<TenantUser> list = tenantUserMapper.selectList(
                new LambdaQueryWrapper<TenantUser>()
                        .eq(TenantUser::getTenantId, tenantId)
                        .eq(TenantUser::getStatus, 1)
                        .orderByAsc(TenantUser::getCreateTime)
        );
        return list.stream().map(this::toMemberVO).toList();
    }

    // ─────────────────────────── 转换工具 ───────────────────────────

    private TenantVO toVO(Tenant t) {
        TenantVO vo = new TenantVO();
        vo.setId(t.getId());
        vo.setName(t.getName());
        vo.setPlan(t.getPlan());
        vo.setStatus(t.getStatus());
        vo.setCreateTime(t.getCreateTime());
        vo.setUpdateTime(t.getUpdateTime());
        return vo;
    }

    private MemberVO toMemberVO(TenantUser tu) {
        MemberVO vo = new MemberVO();
        vo.setId(tu.getId());
        vo.setTenantId(tu.getTenantId());
        vo.setUserId(tu.getUserId());
        vo.setRole(tu.getRole());
        vo.setStatus(tu.getStatus());
        vo.setCreateTime(tu.getCreateTime());
        return vo;
    }
}
