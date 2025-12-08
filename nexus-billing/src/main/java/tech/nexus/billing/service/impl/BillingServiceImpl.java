package tech.nexus.billing.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tech.nexus.billing.dto.*;
import tech.nexus.billing.entity.Plan;
import tech.nexus.billing.entity.TenantQuota;
import tech.nexus.billing.entity.UsageDaily;
import tech.nexus.billing.mapper.PlanMapper;
import tech.nexus.billing.mapper.TenantQuotaMapper;
import tech.nexus.billing.mapper.UsageDailyMapper;
import tech.nexus.billing.service.BillingService;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.ResultCode;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * 计费服务实现。
 *
 * <p>配额检查采用「消耗型」模式：
 * <ol>
 *   <li>Redis INCR 当日调用计数</li>
 *   <li>若超限 → DECR 回滚，返回 allowed=false</li>
 *   <li>若超 Token 限制 → 同样回滚，返回 allowed=false</li>
 * </ol>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class BillingServiceImpl implements BillingService {

    private static final String KEY_CALLS  = "nexus:%d:quota:calls:%s";
    private static final String KEY_TOKENS = "nexus:%d:quota:tokens:%s";
    private static final DateTimeFormatter DATE_FMT = DateTimeFormatter.ofPattern("yyyyMMdd");

    private final PlanMapper planMapper;
    private final TenantQuotaMapper tenantQuotaMapper;
    private final UsageDailyMapper usageDailyMapper;
    private final StringRedisTemplate redisTemplate;

    // ─── 配额检查 ───────────────────────────────────────────────────────────

    @Override
    public CheckQuotaResponse checkQuota(CheckQuotaRequest request) {
        Long tenantId = request.getTenantId();
        long estimatedTokens = request.getEstimatedTokens() == null ? 0L : request.getEstimatedTokens();

        TenantQuota quota = getTenantQuotaOrDefault(tenantId);
        Plan plan = getPlanById(quota.getPlanId());

        long maxCalls  = plan.getMaxApiCallsDay() + (quota.getExtraCalls() == null ? 0 : quota.getExtraCalls());
        long maxTokens = plan.getMaxTokensDay()   + (quota.getExtraTokens() == null ? 0 : quota.getExtraTokens());

        String today      = LocalDate.now().format(DATE_FMT);
        String callsKey   = String.format(KEY_CALLS,  tenantId, today);
        String tokensKey  = String.format(KEY_TOKENS, tenantId, today);

        // 1. 先自增调用计数
        long currentCalls = redisTemplate.opsForValue().increment(callsKey);
        setExpireIfNew(callsKey, currentCalls);

        if (currentCalls > maxCalls) {
            // 超限，回滚
            redisTemplate.opsForValue().decrement(callsKey);
            long usedCalls = currentCalls - 1;
            return CheckQuotaResponse.builder()
                    .allowed(false)
                    .remainingCalls(Math.max(0, maxCalls - usedCalls))
                    .remainingTokens(getRemainingTokens(tokensKey, maxTokens))
                    .reason("每日 API 调用次数已达上限（" + maxCalls + " 次）")
                    .build();
        }

        // 2. 若有 estimatedTokens，检查 Token 限制
        if (estimatedTokens > 0) {
            long currentTokens = redisTemplate.opsForValue().increment(tokensKey, estimatedTokens);
            setExpireIfNew(tokensKey, currentTokens);

            if (currentTokens > maxTokens) {
                // Token 超限，回滚两个计数
                redisTemplate.opsForValue().decrement(callsKey);
                redisTemplate.opsForValue().increment(tokensKey, -estimatedTokens);
                long usedCalls = currentCalls - 1;
                return CheckQuotaResponse.builder()
                        .allowed(false)
                        .remainingCalls(Math.max(0, maxCalls - usedCalls))
                        .remainingTokens(0L)
                        .reason("每日 Token 消耗已达上限（" + maxTokens + " 个）")
                        .build();
            }

            return CheckQuotaResponse.builder()
                    .allowed(true)
                    .remainingCalls(Math.max(0, maxCalls - currentCalls))
                    .remainingTokens(Math.max(0, maxTokens - currentTokens))
                    .build();
        }

        // 未预估 Token，仅检查调用次数
        long usedTokens = getUsedCounter(tokensKey);
        return CheckQuotaResponse.builder()
                .allowed(true)
                .remainingCalls(Math.max(0, maxCalls - currentCalls))
                .remainingTokens(Math.max(0, maxTokens - usedTokens))
                .build();
    }

    // ─── 用量上报 ───────────────────────────────────────────────────────────

    @Override
    @Transactional
    public void reportUsage(UsageReportRequest request) {
        Long tenantId = request.getTenantId();
        String model  = request.getModel();
        long input    = request.getInputTokens()  == null ? 0L : request.getInputTokens();
        long output   = request.getOutputTokens() == null ? 0L : request.getOutputTokens();
        long total    = input + output;
        LocalDate today = LocalDate.now();

        // 更新 Redis 实时计数（调用已由 checkQuota 计数，此处更新 Token）
        if (total > 0) {
            String tokensKey = String.format(KEY_TOKENS, tenantId, today.format(DATE_FMT));
            long currentTokens = redisTemplate.opsForValue().increment(tokensKey, total);
            setExpireIfNew(tokensKey, currentTokens);
        }

        // UPSERT to usage_daily（ON DUPLICATE KEY UPDATE）
        UsageDaily existing = usageDailyMapper.selectOne(
                new LambdaQueryWrapper<UsageDaily>()
                        .eq(UsageDaily::getTenantId, tenantId)
                        .eq(UsageDaily::getStatDate, today)
                        .eq(UsageDaily::getModel, model));

        if (existing == null) {
            UsageDaily record = new UsageDaily();
            record.setTenantId(tenantId);
            record.setStatDate(today);
            record.setApiCalls(1);
            record.setInputTokens(input);
            record.setOutputTokens(output);
            record.setModel(model);
            record.setCreateTime(LocalDateTime.now());
            record.setUpdateTime(LocalDateTime.now());
            usageDailyMapper.insert(record);
        } else {
            usageDailyMapper.update(null,
                    new LambdaUpdateWrapper<UsageDaily>()
                            .eq(UsageDaily::getId, existing.getId())
                            .setSql("api_calls = api_calls + 1, " +
                                    "input_tokens = input_tokens + " + input + ", " +
                                    "output_tokens = output_tokens + " + output + ", " +
                                    "update_time = NOW()"));
        }

        log.debug("reportUsage tenantId={} model={} input={} output={}", tenantId, model, input, output);
    }

    // ─── 用量查询 ───────────────────────────────────────────────────────────

    @Override
    public UsageQueryResponse queryUsage(Long tenantId, LocalDate startDate, LocalDate endDate) {
        List<UsageSummaryDTO> details = usageDailyMapper.queryUsageSummary(tenantId, startDate, endDate);

        long totalCalls  = details.stream().mapToLong(d -> d.getTotalApiCalls()    == null ? 0 : d.getTotalApiCalls()).sum();
        long totalInput  = details.stream().mapToLong(d -> d.getTotalInputTokens() == null ? 0 : d.getTotalInputTokens()).sum();
        long totalOutput = details.stream().mapToLong(d -> d.getTotalOutputTokens()== null ? 0 : d.getTotalOutputTokens()).sum();

        return UsageQueryResponse.builder()
                .tenantId(tenantId)
                .startDate(startDate.toString())
                .endDate(endDate.toString())
                .totalApiCalls(totalCalls)
                .totalInputTokens(totalInput)
                .totalOutputTokens(totalOutput)
                .dailyDetails(details)
                .build();
    }

    // ─── 配额余量查询 ────────────────────────────────────────────────────────

    @Override
    public QuotaInfoResponse getQuotaInfo(Long tenantId) {
        TenantQuota quota = getTenantQuotaOrDefault(tenantId);
        Plan plan = getPlanById(quota.getPlanId());

        long maxCalls  = plan.getMaxApiCallsDay() + (quota.getExtraCalls()  == null ? 0 : quota.getExtraCalls());
        long maxTokens = plan.getMaxTokensDay()   + (quota.getExtraTokens() == null ? 0 : quota.getExtraTokens());

        String today     = LocalDate.now().format(DATE_FMT);
        long usedCalls   = getUsedCounter(String.format(KEY_CALLS,  tenantId, today));
        long usedTokens  = getUsedCounter(String.format(KEY_TOKENS, tenantId, today));

        return QuotaInfoResponse.builder()
                .tenantId(tenantId)
                .planName(plan.getName())
                .planDisplayName(plan.getDisplayName())
                .maxApiCallsDay(maxCalls)
                .maxTokensDay(maxTokens)
                .usedApiCalls(usedCalls)
                .usedTokens(usedTokens)
                .remainingCalls(Math.max(0, maxCalls - usedCalls))
                .remainingTokens(Math.max(0, maxTokens - usedTokens))
                .validUntil(quota.getValidUntil())
                .build();
    }

    // ─── 修改套餐 ─────────────────────────────────────────────────────────────

    @Override
    @Transactional
    public void updateTenantPlan(Long tenantId, UpdatePlanRequest request) {
        Plan plan = planMapper.selectOne(
                new LambdaQueryWrapper<Plan>().eq(Plan::getName, request.getPlanName()));
        if (plan == null) {
            throw new BizException(ResultCode.NOT_FOUND, "套餐不存在: " + request.getPlanName());
        }

        TenantQuota quota = tenantQuotaMapper.selectOne(
                new LambdaQueryWrapper<TenantQuota>().eq(TenantQuota::getTenantId, tenantId));

        if (quota == null) {
            // 新增
            TenantQuota newQuota = new TenantQuota();
            newQuota.setTenantId(tenantId);
            newQuota.setPlanId(plan.getId());
            newQuota.setExtraCalls(0);
            newQuota.setExtraTokens(0L);
            newQuota.setCreateTime(LocalDateTime.now());
            newQuota.setUpdateTime(LocalDateTime.now());
            tenantQuotaMapper.insert(newQuota);
        } else {
            tenantQuotaMapper.update(null,
                    new LambdaUpdateWrapper<TenantQuota>()
                            .eq(TenantQuota::getTenantId, tenantId)
                            .set(TenantQuota::getPlanId, plan.getId())
                            .set(TenantQuota::getUpdateTime, LocalDateTime.now()));
        }

        log.info("updateTenantPlan tenantId={} newPlan={}", tenantId, plan.getName());
    }

    // ─── 私有辅助方法 ─────────────────────────────────────────────────────────

    /**
     * 查询租户配额，若不存在则自动使用 FREE 套餐（懒初始化）
     */
    private TenantQuota getTenantQuotaOrDefault(Long tenantId) {
        TenantQuota quota = tenantQuotaMapper.selectOne(
                new LambdaQueryWrapper<TenantQuota>().eq(TenantQuota::getTenantId, tenantId));
        if (quota != null) return quota;

        // 懒初始化：未配置的租户默认 FREE 套餐
        Plan freePlan = planMapper.selectOne(
                new LambdaQueryWrapper<Plan>().eq(Plan::getName, "FREE"));
        if (freePlan == null) {
            throw new BizException(ResultCode.INTERNAL_ERROR, "系统套餐数据缺失，请联系管理员");
        }

        TenantQuota newQuota = new TenantQuota();
        newQuota.setTenantId(tenantId);
        newQuota.setPlanId(freePlan.getId());
        newQuota.setExtraCalls(0);
        newQuota.setExtraTokens(0L);
        newQuota.setCreateTime(LocalDateTime.now());
        newQuota.setUpdateTime(LocalDateTime.now());
        tenantQuotaMapper.insert(newQuota);
        return newQuota;
    }

    private Plan getPlanById(Long planId) {
        Plan plan = planMapper.selectById(planId);
        if (plan == null) {
            throw new BizException(ResultCode.INTERNAL_ERROR, "套餐数据缺失，planId=" + planId);
        }
        return plan;
    }

    /**
     * 设置 Redis key 的过期时间（仅在首次创建时设置，避免重复调用）。
     * 当 value == 1 或 value == estimatedTokens 时视为「首次」。
     */
    private void setExpireIfNew(String key, long currentValue) {
        if (currentValue <= 1) {
            // 计算到今天 23:59:59 的秒数
            long secondsUntilMidnight = secondsUntilEndOfDay();
            redisTemplate.expire(key, secondsUntilMidnight, TimeUnit.SECONDS);
        }
    }

    private long secondsUntilEndOfDay() {
        LocalDateTime now = LocalDateTime.now();
        LocalDateTime endOfDay = now.toLocalDate().atTime(23, 59, 59);
        return ChronoUnit.SECONDS.between(now, endOfDay);
    }

    private long getUsedCounter(String key) {
        String val = redisTemplate.opsForValue().get(key);
        return val == null ? 0L : Long.parseLong(val);
    }

    private long getRemainingTokens(String tokensKey, long maxTokens) {
        long used = getUsedCounter(tokensKey);
        return Math.max(0, maxTokens - used);
    }
}
