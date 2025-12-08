package tech.nexus.billing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import tech.nexus.billing.entity.TenantQuota;

/**
 * 租户配额 Mapper
 */
@Mapper
public interface TenantQuotaMapper extends BaseMapper<TenantQuota> {
}
