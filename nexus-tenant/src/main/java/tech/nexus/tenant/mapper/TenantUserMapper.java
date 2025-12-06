package tech.nexus.tenant.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import tech.nexus.tenant.entity.TenantUser;

/**
 * 租户成员 Mapper
 */
@Mapper
public interface TenantUserMapper extends BaseMapper<TenantUser> {
}
