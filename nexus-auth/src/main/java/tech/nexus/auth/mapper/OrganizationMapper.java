package tech.nexus.auth.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Param;
import tech.nexus.auth.entity.Organization;

import java.util.List;

/**
 * 组织 Mapper。
 *
 * <p>V5 新增。
 */
public interface OrganizationMapper extends BaseMapper<Organization> {

    /**
     * 按组织代码查询
     */
    Organization findByCode(@Param("code") String code);

    /**
     * 查询用户创建的组织数量
     */
    int countByOwnerId(@Param("ownerId") Long ownerId);
}
