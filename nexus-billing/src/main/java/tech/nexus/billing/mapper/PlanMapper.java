package tech.nexus.billing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import tech.nexus.billing.entity.Plan;

/**
 * 套餐 Mapper
 */
@Mapper
public interface PlanMapper extends BaseMapper<Plan> {
}
