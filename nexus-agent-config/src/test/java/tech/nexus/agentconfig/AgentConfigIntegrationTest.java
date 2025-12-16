package tech.nexus.agentconfig;

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
import tech.nexus.agentconfig.dto.AgentConfigRequest;
import tech.nexus.agentconfig.entity.ToolRegistry;
import tech.nexus.agentconfig.mapper.AgentConfigMapper;
import tech.nexus.agentconfig.mapper.AgentConfigHistoryMapper;
import tech.nexus.agentconfig.mapper.ToolRegistryMapper;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

import static org.hamcrest.Matchers.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultHandlers.print;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * nexus-agent-config 集成测试（H2 内存库，Mock Redis）。
 *
 * <p>覆盖 CLAUDE.md 测试要求：
 * <ul>
 *   <li>创建 Agent → 版本号为 1</li>
 *   <li>更新 Agent → 版本号 +1，历史表有记录</li>
 *   <li>回滚到 v1 → 配置恢复，版本号继续 +1</li>
 *   <li>租户 A 的 Agent 不能被租户 B 查询</li>
 *   <li>is_public=1 的模板所有租户可查询</li>
 * </ul>
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AgentConfigIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private AgentConfigMapper agentConfigMapper;

    @Autowired
    private AgentConfigHistoryMapper historyMapper;

    @Autowired
    private ToolRegistryMapper toolRegistryMapper;

    @MockBean
    private StringRedisTemplate redisTemplate;

    @MockBean
    private ValueOperations<String, String> valueOperations;

    @BeforeEach
    void setUp() {
        // Mock Redis operations
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get(anyString())).thenReturn(null);

        // 清空测试数据
        agentConfigMapper.delete(null);
        historyMapper.delete(null);
    }

    // ────────────────────────────────────────────────────────
    // Test-01: 创建 Agent → 版本号为 1
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("创建 Agent 版本号应为 1")
    void createAgent_versionShouldBe1() throws Exception {
        AgentConfigRequest req = buildRequest("Test Agent", "web_search");

        mockMvc.perform(post("/api/agent-config/agents")
                        .header("X-Tenant-Id", "1001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.version").value(1))
                .andExpect(jsonPath("$.data.name").value("Test Agent"))
                .andExpect(jsonPath("$.data.tenantId").value(1001));
    }

    // ────────────────────────────────────────────────────────
    // Test-02: 更新 Agent → 版本号 +1，历史表有记录
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("更新 Agent 版本号递增且历史表有记录")
    void updateAgent_versionIncreaseAndHistoryCreated() throws Exception {
        // 创建
        AgentConfigRequest createReq = buildRequest("Update Test", "calculator");
        String createResponse = mockMvc.perform(post("/api/agent-config/agents")
                        .header("X-Tenant-Id", "1001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(createReq)))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        Long agentId = objectMapper.readTree(createResponse).path("data").path("id").asLong();

        // 更新
        AgentConfigRequest updateReq = buildRequest("Update Test", "web_search");
        updateReq.setChangeNote("第一次更新");
        mockMvc.perform(put("/api/agent-config/agents/" + agentId)
                        .header("X-Tenant-Id", "1001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(updateReq)))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.version").value(2));

        // 验证历史表有记录
        mockMvc.perform(get("/api/agent-config/agents/" + agentId + "/history")
                        .header("X-Tenant-Id", "1001"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(1)))
                .andExpect(jsonPath("$.data[0].version").value(1));
    }

    // ────────────────────────────────────────────────────────
    // Test-03: 回滚到 v1 → 配置恢复，版本号继续 +1
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("回滚到 v1 后版本号继续递增")
    void rollback_restoreConfigAndVersionContinues() throws Exception {
        // 创建（v1）
        AgentConfigRequest createReq = buildRequest("Rollback Test", "calculator");
        createReq.setSystemPrompt("Original prompt");
        String createResp = mockMvc.perform(post("/api/agent-config/agents")
                        .header("X-Tenant-Id", "1001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(createReq)))
                .andReturn().getResponse().getContentAsString();
        Long agentId = objectMapper.readTree(createResp).path("data").path("id").asLong();

        // 更新（v2）
        AgentConfigRequest updateReq = buildRequest("Rollback Test", "web_search");
        updateReq.setSystemPrompt("Modified prompt");
        mockMvc.perform(put("/api/agent-config/agents/" + agentId)
                        .header("X-Tenant-Id", "1001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(updateReq)))
                .andExpect(jsonPath("$.data.version").value(2));

        // 回滚到 v1（应变为 v3）
        mockMvc.perform(post("/api/agent-config/agents/" + agentId + "/rollback/1")
                        .header("X-Tenant-Id", "1001"))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.version").value(3))
                .andExpect(jsonPath("$.data.systemPrompt").value("Original prompt"));
    }

    // ────────────────────────────────────────────────────────
    // Test-04: 租户 A 的 Agent 不能被租户 B 查询
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("租户隔离：租户 B 不能查询租户 A 的 Agent")
    void tenantIsolation_tenantBCannotAccessTenantA() throws Exception {
        // 租户 A 创建 Agent
        AgentConfigRequest req = buildRequest("Tenant A Agent", "calculator");
        String resp = mockMvc.perform(post("/api/agent-config/agents")
                        .header("X-Tenant-Id", "2001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(jsonPath("$.data.tenantId").value(2001))
                .andReturn().getResponse().getContentAsString();
        Long agentId = objectMapper.readTree(resp).path("data").path("id").asLong();

        // 租户 B 尝试查询应返回 403
        mockMvc.perform(get("/api/agent-config/agents/" + agentId)
                        .header("X-Tenant-Id", "2002"))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(403));
    }

    // ────────────────────────────────────────────────────────
    // Test-05: is_public=1 的模板所有租户可查询
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("公共模板对所有租户可见")
    void publicTemplate_visibleToAllTenants() throws Exception {
        // 租户 A 创建公共模板
        AgentConfigRequest req = buildRequest("Public Template", "web_search");
        req.setIsPublic(1);
        req.setStatus(1);
        mockMvc.perform(post("/api/agent-config/agents")
                        .header("X-Tenant-Id", "3001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(jsonPath("$.data.isPublic").value(1));

        // 租户 B 可查询模板列表
        mockMvc.perform(get("/api/agent-config/templates")
                        .header("X-Tenant-Id", "3002"))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(greaterThanOrEqualTo(1))));
    }

    // ────────────────────────────────────────────────────────
    // Test-06: temperature 范围校验
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("temperature 超出范围返回参数错误")
    void temperatureValidation_outOfRange() throws Exception {
        AgentConfigRequest req = buildRequest("Temp Test", "calculator");
        req.setTemperature(new BigDecimal("3.0")); // 超出范围

        mockMvc.perform(post("/api/agent-config/agents")
                        .header("X-Tenant-Id", "1001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(400));
    }

    // ────────────────────────────────────────────────────────
    // Test-07: 使用未注册工具返回错误
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("使用未注册工具名应返回参数错误")
    void unregisteredTool_shouldFail() throws Exception {
        AgentConfigRequest req = buildRequest("Tool Test", "nonexistent_tool_xyz");

        mockMvc.perform(post("/api/agent-config/agents")
                        .header("X-Tenant-Id", "1001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(400));
    }

    // ────────────────────────────────────────────────────────
    // Test-08: Fork 公共模板
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("Fork 模板创建私有副本")
    void forkTemplate_createPrivateCopy() throws Exception {
        // 创建公共模板
        AgentConfigRequest req = buildRequest("Fork Template", "calculator");
        req.setIsPublic(1);
        req.setStatus(1);
        String resp = mockMvc.perform(post("/api/agent-config/agents")
                        .header("X-Tenant-Id", "4001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andReturn().getResponse().getContentAsString();
        Long templateId = objectMapper.readTree(resp).path("data").path("id").asLong();

        // 租户 B Fork 模板
        mockMvc.perform(post("/api/agent-config/templates/" + templateId + "/fork")
                        .header("X-Tenant-Id", "4002"))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.tenantId").value(4002))
                .andExpect(jsonPath("$.data.isPublic").value(0))
                .andExpect(jsonPath("$.data.version").value(1));
    }

    // ────────────────────────────────────────────────────────
    // Test-09: Agent 列表分页
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("分页列出租户 Agent 列表")
    void listAgents_pagination() throws Exception {
        long tenantId = 5001L;
        for (int i = 1; i <= 3; i++) {
            AgentConfigRequest req = buildRequest("Agent-" + i, "calculator");
            mockMvc.perform(post("/api/agent-config/agents")
                    .header("X-Tenant-Id", tenantId)
                    .contentType(MediaType.APPLICATION_JSON)
                    .content(objectMapper.writeValueAsString(req)));
        }

        // 验证分页接口返回成功且记录列表不为空
        mockMvc.perform(get("/api/agent-config/agents")
                        .header("X-Tenant-Id", tenantId)
                        .param("page", "1")
                        .param("size", "2"))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.records").isArray())
                .andExpect(jsonPath("$.data.records", hasSize(greaterThanOrEqualTo(1))))
                .andExpect(jsonPath("$.data.current").value(1))
                .andExpect(jsonPath("$.data.size").value(2));
    }

    // ────────────────────────────────────────────────────────
    // Test-10: 删除 Agent
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("删除 Agent 后再查询返回 404")
    void deleteAgent_thenGetReturns404() throws Exception {
        AgentConfigRequest req = buildRequest("Delete Test", "calculator");
        String resp = mockMvc.perform(post("/api/agent-config/agents")
                        .header("X-Tenant-Id", "6001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andReturn().getResponse().getContentAsString();
        Long agentId = objectMapper.readTree(resp).path("data").path("id").asLong();

        // 删除
        mockMvc.perform(delete("/api/agent-config/agents/" + agentId)
                        .header("X-Tenant-Id", "6001"))
                .andExpect(jsonPath("$.code").value(200));

        // 再查询应返回 404
        mockMvc.perform(get("/api/agent-config/agents/" + agentId)
                        .header("X-Tenant-Id", "6001"))
                .andExpect(jsonPath("$.code").value(404));
    }

    // ────────────────────────────────────────────────────────
    // Helper
    // ────────────────────────────────────────────────────────

    private AgentConfigRequest buildRequest(String name, String... tools) {
        AgentConfigRequest req = new AgentConfigRequest();
        req.setName(name);
        req.setDescription("Test description");
        req.setSystemPrompt("You are a helpful assistant.");
        req.setModel("MiniMax-M2.5-highspeed");
        req.setTemperature(new BigDecimal("0.7"));
        req.setMaxTokens(2000);
        req.setTools(List.of(tools));
        req.setStatus(1);
        req.setIsPublic(0);
        return req;
    }
}
