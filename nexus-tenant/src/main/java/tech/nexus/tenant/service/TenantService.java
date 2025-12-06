package tech.nexus.tenant.service;

import tech.nexus.tenant.dto.*;

import java.util.List;

/**
 * 租户服务接口
 */
public interface TenantService {

    /**
     * 创建租户（系统管理员调用）
     *
     * @param req 创建请求
     * @return 新租户 VO
     */
    TenantVO createTenant(CreateTenantRequest req);

    /**
     * 查询租户
     *
     * @param id 租户 ID
     * @return 租户 VO
     */
    TenantVO getTenant(Long id);

    /**
     * 更新租户配置
     *
     * @param id  租户 ID
     * @param req 更新请求
     * @return 更新后 VO
     */
    TenantVO updateTenant(Long id, UpdateTenantRequest req);

    /**
     * 添加成员（幂等：已存在则更新 role/status）
     *
     * @param tenantId 租户 ID
     * @param req      添加请求
     * @return 成员 VO
     */
    MemberVO addMember(Long tenantId, AddMemberRequest req);

    /**
     * 移除成员（软删除：status=0）
     *
     * @param tenantId 租户 ID
     * @param userId   用户 ID
     */
    void removeMember(Long tenantId, Long userId);

    /**
     * 查询租户成员列表（仅 status=1 的有效成员）
     *
     * @param tenantId 租户 ID
     * @return 成员 VO 列表
     */
    List<MemberVO> listMembers(Long tenantId);
}
