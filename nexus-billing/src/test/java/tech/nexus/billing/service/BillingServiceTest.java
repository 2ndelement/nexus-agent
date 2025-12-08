package tech.nexus.billing.service;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.test.context.ActiveProfiles;
import tech.nexus.billing.dto.*;
import tech.nexus.billing.entity.TenantQuota;
import tech.nexus.billing.mapper.PlanMapper;
import tech.nexus.billing.mapper.TenantQuotaMapper;
import tech.nexus.billing.mapper.UsageDailyMapper;
import tech.nexus.common.exception.BizException;

import java.time.LocalDate;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * BillingService 服务层测试。
 * H2 内存数据库 + Redis MockBean。
 */
@SpringBootTest
@ActiveProfiles("test")
@DisplayName("BillingService 服务层测试")
class BillingServiceTest {

    @Autowired
    private BillingService billingService;

    @Autowired
    private TenantQuotaMapper tenantQuotaMapper;

    @Autowired
    private UsageDailyMapper usageDailyMapper;

    @Autowired
    private PlanMapper planMapper;

    @MockBean
    private StringRedisTemplate redisTemplate;

    @SuppressWarnings("unchecked")
    private final ValueOperations<String, String> valueOps =
            (ValueOperations<String, String>) mock(ValueOperations.class);

    @BeforeEach
    void setUp() {
        when(redisTemplate.opsForValue()).thenReturn(valueOps);
        // 默认：计数器从 0 开始，每次 INCR 返回 1
        when(valueOps.increment(anyString())).thenReturn(1L);
        when(valueOps.increment(anyString(), anyLong())).thenReturn(1L);
        when(valueOps.decrement(anyString())).thenReturn(0L);
        when(valueOps.get(anyString())).thenReturn(null);
        when(redisTemplate.expire(anyString(), anyLong(), any(TimeUnit.class))).thenReturn(true);

        // 清空测试数据
        tenantQuotaMapper.delete(null);
        usageDailyMapper.delete(null);
    }

    // ── 配额检查 - 未超限 ─────────────────────────────────────────────────

    @Test
    @DisplayName("配额检查：调用次数未超限 → allowed=true")
    void checkQuota_notExceeded_returnsAllowed() {
        // FREE 套餐 max_api_calls_day=10，模拟当前是第 1 次调用
        when(valueOps.increment(anyString())).thenReturn(1L);

        CheckQuotaRequest req = new CheckQuotaRequest();
        req.setTenantId(1001L);
        req.setEstimatedTokens(0L);

        CheckQuotaResponse resp = billingService.checkQuota(req);

        assertThat(resp.isAllowed()).isTrue();
        assertThat(resp.getRemainingCalls()).isGreaterThanOrEqualTo(0);
    }

    @Test
    @DisplayName("配额检查：调用次数超限 → allowed=false，并回滚 DECR")
    void checkQuota_callsExceeded_returnsNotAllowed() {
        // FREE 套餐 max_api_calls_day=10，模拟第 11 次调用
        when(valueOps.increment(anyString())).thenReturn(11L);

        CheckQuotaRequest req = new CheckQuotaRequest();
        req.setTenantId(1002L);
        req.setEstimatedTokens(0L);

        CheckQuotaResponse resp = billingService.checkQuota(req);

        assertThat(resp.isAllowed()).isFalse();
        assertThat(resp.getRemainingCalls()).isEqualTo(0L);
        assertThat(resp.getReason()).contains("调用次数");
        // 验证回滚 DECR 被调用
        verify(valueOps, atLeastOnce()).decrement(anyString());
    }

    @Test
    @DisplayName("配额检查：Token 超限 → allowed=false，两个计数均回滚")
    void checkQuota_tokensExceeded_returnsNotAllowed() {
        // 调用次数正常（1 次），但 Token 超限（估计 500，当前已用 1000，超过 FREE 套餐 1000 限制）
        when(valueOps.increment(anyString())).thenReturn(1L);
        when(valueOps.increment(anyString(), anyLong())).thenReturn(1001L); // 超 1000 Token 限

        CheckQuotaRequest req = new CheckQuotaRequest();
        req.setTenantId(1003L);
        req.setEstimatedTokens(500L);

        CheckQuotaResponse resp = billingService.checkQuota(req);

        assertThat(resp.isAllowed()).isFalse();
        assertThat(resp.getReason()).contains("Token");
        // 调用次数和 Token 都需要回滚
        verify(valueOps, atLeastOnce()).decrement(anyString());
        verify(valueOps, atLeastOnce()).increment(anyString(), eq(-500L));
    }

    // ── 配额检查 - 不同租户隔离 ──────────────────────────────────────────────

    @Test
    @DisplayName("不同租户配额计数完全独立")
    void checkQuota_differentTenants_isolatedCounters() {
        // 模拟两个不同租户各自的 Redis key 独立计数
        when(valueOps.increment(contains(":1101:"))).thenReturn(1L);
        when(valueOps.increment(contains(":1102:"))).thenReturn(1L);

        CheckQuotaRequest req1 = new CheckQuotaRequest();
        req1.setTenantId(1101L);
        req1.setEstimatedTokens(0L);

        CheckQuotaRequest req2 = new CheckQuotaRequest();
        req2.setTenantId(1102L);
        req2.setEstimatedTokens(0L);

        CheckQuotaResponse resp1 = billingService.checkQuota(req1);
        CheckQuotaResponse resp2 = billingService.checkQuota(req2);

        assertThat(resp1.isAllowed()).isTrue();
        assertThat(resp2.isAllowed()).isTrue();
    }

    // ── Redis EXPIRE 必须设置 ─────────────────────────────────────────────

    @Test
    @DisplayName("Redis INCR 首次（value=1）必须设置 EXPIRE")
    void checkQuota_firstIncr_setsExpire() {
        when(valueOps.increment(anyString())).thenReturn(1L);

        CheckQuotaRequest req = new CheckQuotaRequest();
        req.setTenantId(1004L);
        req.setEstimatedTokens(0L);

        billingService.checkQuota(req);

        // 验证 expire 被调用（防止 key 永久存在）
        verify(redisTemplate, atLeastOnce()).expire(anyString(), anyLong(), eq(TimeUnit.SECONDS));
    }

    // ── 用量上报 ─────────────────────────────────────────────────────────

    @Test
    @DisplayName("用量上报：新记录正确插入 usage_daily")
    void reportUsage_newRecord_insertsRow() {
        UsageReportRequest req = new UsageReportRequest();
        req.setTenantId(2001L);
        req.setModel("gpt-4o");
        req.setInputTokens(100L);
        req.setOutputTokens(300L);

        billingService.reportUsage(req);

        var records = usageDailyMapper.selectList(null);
        assertThat(records).hasSize(1);
        assertThat(records.get(0).getTenantId()).isEqualTo(2001L);
        assertThat(records.get(0).getApiCalls()).isEqualTo(1);
        assertThat(records.get(0).getInputTokens()).isEqualTo(100L);
        assertThat(records.get(0).getOutputTokens()).isEqualTo(300L);
    }

    @Test
    @DisplayName("用量上报：同一租户同一天同一模型重复上报 → 累加而非覆盖")
    void reportUsage_sameDay_accumulates() {
        UsageReportRequest req = new UsageReportRequest();
        req.setTenantId(2002L);
        req.setModel("claude-3-5-sonnet");
        req.setInputTokens(100L);
        req.setOutputTokens(200L);

        billingService.reportUsage(req);
        billingService.reportUsage(req);

        var records = usageDailyMapper.selectList(null);
        assertThat(records).hasSize(1);
        assertThat(records.get(0).getApiCalls()).isEqualTo(2);
        assertThat(records.get(0).getInputTokens()).isEqualTo(200L);
        assertThat(records.get(0).getOutputTokens()).isEqualTo(400L);
    }

    @Test
    @DisplayName("用量上报：不同模型产生不同记录行")
    void reportUsage_differentModels_separateRows() {
        UsageReportRequest req1 = buildReportReq(2003L, "model-a", 100L, 200L);
        UsageReportRequest req2 = buildReportReq(2003L, "model-b", 50L,  100L);

        billingService.reportUsage(req1);
        billingService.reportUsage(req2);

        var records = usageDailyMapper.selectList(null);
        assertThat(records).hasSize(2);
    }

    // ── 用量查询 ─────────────────────────────────────────────────────────

    @Test
    @DisplayName("用量查询：按日期范围正确聚合")
    void queryUsage_correctAggregation() {
        billingService.reportUsage(buildReportReq(3001L, "gpt-4", 100L, 200L));

        LocalDate today = LocalDate.now();
        UsageQueryResponse resp = billingService.queryUsage(3001L, today, today);

        assertThat(resp.getTenantId()).isEqualTo(3001L);
        assertThat(resp.getTotalApiCalls()).isGreaterThanOrEqualTo(1);
        assertThat(resp.getDailyDetails()).isNotEmpty();
    }

    @Test
    @DisplayName("用量查询：无数据时返回空列表且汇总为0")
    void queryUsage_noData_returnsZero() {
        LocalDate today = LocalDate.now();
        UsageQueryResponse resp = billingService.queryUsage(9999L, today, today);

        assertThat(resp.getTotalApiCalls()).isEqualTo(0);
        assertThat(resp.getDailyDetails()).isEmpty();
    }

    // ── 配额余量查询 ─────────────────────────────────────────────────────

    @Test
    @DisplayName("配额余量查询：未配置租户默认 FREE 套餐")
    void getQuotaInfo_unconfiguredTenant_usesFreeplan() {
        when(valueOps.get(anyString())).thenReturn(null);

        QuotaInfoResponse resp = billingService.getQuotaInfo(4001L);

        assertThat(resp.getPlanName()).isEqualTo("FREE");
        assertThat(resp.getMaxApiCallsDay()).isEqualTo(10L); // H2 schema 中 FREE = 10
        assertThat(resp.getUsedApiCalls()).isEqualTo(0L);
        assertThat(resp.getRemainingCalls()).isEqualTo(10L);
    }

    @Test
    @DisplayName("配额余量查询：已使用部分配额后余量正确")
    void getQuotaInfo_partiallyUsed_correctRemaining() {
        when(valueOps.get(contains(":quota:calls:"))).thenReturn("3");
        when(valueOps.get(contains(":quota:tokens:"))).thenReturn("500");

        QuotaInfoResponse resp = billingService.getQuotaInfo(4002L);

        assertThat(resp.getUsedApiCalls()).isEqualTo(3L);
        assertThat(resp.getRemainingCalls()).isEqualTo(resp.getMaxApiCallsDay() - 3);
    }

    // ── 修改套餐 ─────────────────────────────────────────────────────────

    @Test
    @DisplayName("修改套餐：未存在的租户 → 新建 TenantQuota 记录")
    void updateTenantPlan_newTenant_createsQuota() {
        UpdatePlanRequest req = new UpdatePlanRequest();
        req.setPlanName("PRO");

        billingService.updateTenantPlan(5001L, req);

        TenantQuota quota = tenantQuotaMapper.selectList(null).stream()
                .filter(q -> q.getTenantId().equals(5001L))
                .findFirst().orElse(null);
        assertThat(quota).isNotNull();
        // PRO 套餐 id=2（按 schema-h2.sql 插入顺序）
        var proPlan = planMapper.selectList(null).stream()
                .filter(p -> "PRO".equals(p.getName())).findFirst().orElseThrow();
        assertThat(quota.getPlanId()).isEqualTo(proPlan.getId());
    }

    @Test
    @DisplayName("修改套餐：已有套餐 → 更新 plan_id")
    void updateTenantPlan_existingTenant_updatesPlan() {
        // 先设置 FREE
        UpdatePlanRequest freeReq = new UpdatePlanRequest();
        freeReq.setPlanName("FREE");
        billingService.updateTenantPlan(5002L, freeReq);

        // 再升级为 ENTERPRISE
        UpdatePlanRequest entReq = new UpdatePlanRequest();
        entReq.setPlanName("ENTERPRISE");
        billingService.updateTenantPlan(5002L, entReq);

        TenantQuota quota = tenantQuotaMapper.selectList(null).stream()
                .filter(q -> q.getTenantId().equals(5002L))
                .findFirst().orElseThrow();
        var entPlan = planMapper.selectList(null).stream()
                .filter(p -> "ENTERPRISE".equals(p.getName())).findFirst().orElseThrow();
        assertThat(quota.getPlanId()).isEqualTo(entPlan.getId());
    }

    @Test
    @DisplayName("修改套餐：套餐名不存在 → 抛出 BizException")
    void updateTenantPlan_invalidPlan_throwsBizException() {
        UpdatePlanRequest req = new UpdatePlanRequest();
        req.setPlanName("ULTRA");

        assertThatThrownBy(() -> billingService.updateTenantPlan(5003L, req))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("套餐不存在");
    }

    // ── 辅助方法 ─────────────────────────────────────────────────────────

    private UsageReportRequest buildReportReq(Long tenantId, String model,
                                               Long inputTokens, Long outputTokens) {
        UsageReportRequest req = new UsageReportRequest();
        req.setTenantId(tenantId);
        req.setModel(model);
        req.setInputTokens(inputTokens);
        req.setOutputTokens(outputTokens);
        return req;
    }
}
