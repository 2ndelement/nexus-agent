package tech.nexus.auth.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Param;
import tech.nexus.auth.dto.TokenResponse.OrganizationWithRole;
import tech.nexus.auth.entity.OrganizationUser;

import java.util.List;

/**
 * 组织成员 Mapper。
 *
 * <p>V5 新增。
 */
public interface OrganizationUserMapper extends BaseMapper<OrganizationUser> {

    /**
     * 查询用户加入的组织列表（含角色）
     */
    List<OrganizationWithRole> findOrganizationsByUserId(@Param("userId") Long userId);

    /**
     * 查询用户加入的组织数量
     */
    int countByUserId(@Param("userId") Long userId);

    /**
     * 查询用户在指定组织的成员关系
     */
    OrganizationUser findByOrgAndUser(@Param("organizationId") Long organizationId,
                                      @Param("userId") Long userId);
}
