package tech.nexus.billing.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import tech.nexus.billing.mapper.TenantQuotaMapper;
import tech.nexus.billing.mapper.UsageDailyMapper;

import java.util.concurrent.TimeUnit;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * BillingController Web 层测试（MockMvc）。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DisplayName("BillingController Web 层测试")
class BillingControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private TenantQuotaMapper tenantQuotaMapper;

    @Autowired
    private UsageDailyMapper usageDailyMapper;

    @MockBean
    private StringRedisTemplate redisTemplate;

    @SuppressWarnings("unchecked")
    private final ValueOperations<String, String> valueOps =
            (ValueOperations<String, String>) mock(ValueOperations.class);

    @BeforeEach
    void setUp() {
        when(redisTemplate.opsForValue()).thenReturn(valueOps);
        when(valueOps.increment(anyString())).thenReturn(1L);
        when(valueOps.increment(anyString(), anyLong())).thenReturn(1L);
        when(valueOps.decrement(anyString())).thenReturn(0L);
        when(valueOps.get(anyString())).thenReturn(null);
        when(redisTemplate.expire(anyString(), anyLong(), any(TimeUnit.class))).thenReturn(true);

        tenantQuotaMapper.delete(null);
        usageDailyMapper.delete(null);
    }

    // ── /check-quota ────────────────────────────────────────────────────

    @Test
    @DisplayName("POST /check-quota：配额充足 → 200 + allowed=true")
    void checkQuota_allowed_returns200() throws Exception {
        when(valueOps.increment(anyString())).thenReturn(1L); // 未超限

        mockMvc.perform(post("/api/billing/check-quota")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"tenantId": 100, "estimatedTokens": 0}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.allowed").value(true));
    }

    @Test
    @DisplayName("POST /check-quota：配额超限 → 429")
    void checkQuota_exceeded_returns429() throws Exception {
        when(valueOps.increment(anyString())).thenReturn(999L); // 超过 FREE 套餐 10 次

        mockMvc.perform(post("/api/billing/check-quota")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"tenantId": 101, "estimatedTokens": 0}
                                """))
                .andExpect(status().isTooManyRequests());
    }

    @Test
    @DisplayName("POST /check-quota：tenantId 为空 → 400")
    void checkQuota_missingTenantId_returns400() throws Exception {
        mockMvc.perform(post("/api/billing/check-quota")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"estimatedTokens": 0}
                                """))
                .andExpect(status().isBadRequest());
    }

    // ── /usage/report ───────────────────────────────────────────────────

    @Test
    @DisplayName("POST /usage/report：参数合法 → 200")
    void reportUsage_valid_returns200() throws Exception {
        mockMvc.perform(post("/api/billing/usage/report")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"tenantId": 200, "model": "gpt-4o", "inputTokens": 100, "outputTokens": 300}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));
    }

    @Test
    @DisplayName("POST /usage/report：model 为空 → 400")
    void reportUsage_missingModel_returns400() throws Exception {
        mockMvc.perform(post("/api/billing/usage/report")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"tenantId": 200, "inputTokens": 100, "outputTokens": 300}
                                """))
                .andExpect(status().isBadRequest());
    }

    // ── /usage ──────────────────────────────────────────────────────────

    @Test
    @DisplayName("GET /usage：正常查询 → 200")
    void queryUsage_valid_returns200() throws Exception {
        mockMvc.perform(get("/api/billing/usage")
                        .param("tenantId", "300")
                        .param("startDate", "2026-03-01")
                        .param("endDate", "2026-03-17"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.tenantId").value(300));
    }

    @Test
    @DisplayName("GET /usage：startDate > endDate → 400")
    void queryUsage_invalidDateRange_returns400() throws Exception {
        mockMvc.perform(get("/api/billing/usage")
                        .param("tenantId", "300")
                        .param("startDate", "2026-03-17")
                        .param("endDate", "2026-03-01"))
                .andExpect(status().isBadRequest());
    }

    // ── /quota ──────────────────────────────────────────────────────────

    @Test
    @DisplayName("GET /quota：返回租户配额余量信息")
    void getQuotaInfo_returns200WithInfo() throws Exception {
        when(valueOps.get(anyString())).thenReturn(null);

        mockMvc.perform(get("/api/billing/quota")
                        .param("tenantId", "400"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.planName").value("FREE"))
                .andExpect(jsonPath("$.data.tenantId").value(400));
    }

    // ── /tenants/{id}/plan ───────────────────────────────────────────────

    @Test
    @DisplayName("PUT /tenants/{id}/plan：修改为 PRO → 200")
    void updatePlan_validPlan_returns200() throws Exception {
        mockMvc.perform(put("/api/billing/tenants/500/plan")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"planName": "PRO"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));
    }

    @Test
    @DisplayName("PUT /tenants/{id}/plan：套餐不存在 → 404")
    void updatePlan_invalidPlan_returns404() throws Exception {
        mockMvc.perform(put("/api/billing/tenants/500/plan")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"planName": "SUPER_ULTRA"}
                                """))
                .andExpect(status().isNotFound());
    }
}
