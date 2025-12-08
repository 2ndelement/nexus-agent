package tech.nexus.billing.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import tech.nexus.billing.dto.UsageSummaryDTO;
import tech.nexus.billing.entity.UsageDaily;

import java.time.LocalDate;
import java.util.List;

/**
 * 每日用量 Mapper
 */
@Mapper
public interface UsageDailyMapper extends BaseMapper<UsageDaily> {

    /**
     * 按日期范围聚合查询用量汇总
     */
    @Select("SELECT stat_date, SUM(api_calls) AS totalApiCalls, " +
            "SUM(input_tokens) AS totalInputTokens, SUM(output_tokens) AS totalOutputTokens " +
            "FROM usage_daily " +
            "WHERE tenant_id = #{tenantId} AND stat_date BETWEEN #{startDate} AND #{endDate} " +
            "GROUP BY stat_date " +
            "ORDER BY stat_date")
    List<UsageSummaryDTO> queryUsageSummary(@Param("tenantId") Long tenantId,
                                            @Param("startDate") LocalDate startDate,
                                            @Param("endDate") LocalDate endDate);
}
