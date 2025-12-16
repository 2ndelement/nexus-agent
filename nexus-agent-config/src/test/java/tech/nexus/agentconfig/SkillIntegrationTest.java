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
import tech.nexus.agentconfig.dto.SkillRequest;
import tech.nexus.agentconfig.mapper.AgentSkillMapper;
import tech.nexus.agentconfig.mapper.SkillMapper;

import static org.hamcrest.Matchers.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultHandlers.print;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Skill 系统集成测试。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class SkillIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private SkillMapper skillMapper;

    @Autowired
    private AgentSkillMapper agentSkillMapper;

    @MockBean
    private StringRedisTemplate redisTemplate;

    @MockBean
    private ValueOperations<String, String> valueOperations;

    @BeforeEach
    void setUp() {
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get(anyString())).thenReturn(null);

        agentSkillMapper.delete(null);
        skillMapper.delete(null);
    }

    // ────────────────────────────────────────────────────────
    // Test-S1: 创建 Skill
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("创建 Skill 成功，文件写入本地")
    void createSkill_success() throws Exception {
        SkillRequest req = buildSkillRequest("my-skill", "A skill for testing purposes");

        mockMvc.perform(post("/api/agent-config/skills")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.name").value("my-skill"))
                .andExpect(jsonPath("$.data.description").isNotEmpty())
                .andExpect(jsonPath("$.data.filePath").value(containsString("my-skill")));
    }

    // ────────────────────────────────────────────────────────
    // Test-S2: 重复创建同名 Skill 失败
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("重复创建同名 Skill 应返回错误")
    void createSkill_duplicateName_shouldFail() throws Exception {
        SkillRequest req = buildSkillRequest("dup-skill", "Duplicate skill");

        mockMvc.perform(post("/api/agent-config/skills")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(req)));

        mockMvc.perform(post("/api/agent-config/skills")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andDo(print())
                .andExpect(jsonPath("$.code").value(400));
    }

    // ────────────────────────────────────────────────────────
    // Test-S3: RAG 关键词检索
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("RAG 关键词检索匹配 description")
    void searchSkill_byKeyword() throws Exception {
        // 创建两个 Skill
        mockMvc.perform(post("/api/agent-config/skills")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(
                        buildSkillRequest("pdf-tool", "Tool for processing PDF documents"))));
        mockMvc.perform(post("/api/agent-config/skills")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(
                        buildSkillRequest("excel-tool", "Tool for Excel spreadsheet operations"))));

        // 搜索 PDF
        mockMvc.perform(get("/api/agent-config/skills/search").param("query", "PDF"))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(1)))
                .andExpect(jsonPath("$.data[0].name").value("pdf-tool"));
    }

    // ────────────────────────────────────────────────────────
    // Test-S4: Agent-Skill 绑定
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("绑定 Skill 到 Agent 并查询绑定列表")
    void bindSkillToAgent_andList() throws Exception {
        // 创建 Skill
        mockMvc.perform(post("/api/agent-config/skills")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(
                        buildSkillRequest("bind-skill", "Skill for binding test"))));

        Long agentId = 9001L;

        // 绑定
        mockMvc.perform(post("/api/agent-config/skills/bind/" + agentId + "/bind-skill"))
                .andDo(print())
                .andExpect(jsonPath("$.code").value(200));

        // 查询绑定列表
        mockMvc.perform(get("/api/agent-config/skills/agent/" + agentId))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(1)))
                .andExpect(jsonPath("$.data[0].name").value("bind-skill"));
    }

    // ────────────────────────────────────────────────────────
    // Test-S5: 解绑 Skill
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("解绑 Skill 后绑定列表为空")
    void unbindSkill_listBecomesEmpty() throws Exception {
        mockMvc.perform(post("/api/agent-config/skills")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(
                        buildSkillRequest("unbind-skill", "Skill for unbind test"))));

        Long agentId = 9002L;
        mockMvc.perform(post("/api/agent-config/skills/bind/" + agentId + "/unbind-skill"));

        // 解绑
        mockMvc.perform(delete("/api/agent-config/skills/bind/" + agentId + "/unbind-skill"))
                .andExpect(jsonPath("$.code").value(200));

        // 绑定列表为空
        mockMvc.perform(get("/api/agent-config/skills/agent/" + agentId))
                .andExpect(jsonPath("$.data", hasSize(0)));
    }

    // ────────────────────────────────────────────────────────
    // Test-S6: 更新 Skill
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("更新 Skill 内容")
    void updateSkill_success() throws Exception {
        mockMvc.perform(post("/api/agent-config/skills")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(
                        buildSkillRequest("update-skill", "Original description"))));

        SkillRequest updateReq = buildSkillRequest("update-skill", "Updated description");
        updateReq.setContent("---\nname: update-skill\ndescription: Updated description\n---\n# Updated\n");

        mockMvc.perform(put("/api/agent-config/skills/update-skill")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(updateReq)))
                .andDo(print())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.description").value("Updated description"));
    }

    // ────────────────────────────────────────────────────────
    // Test-S7: 删除 Skill
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("删除 Skill 后查询返回 404")
    void deleteSkill_thenGetReturns404() throws Exception {
        mockMvc.perform(post("/api/agent-config/skills")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(
                        buildSkillRequest("del-skill", "To be deleted"))));

        mockMvc.perform(delete("/api/agent-config/skills/del-skill"))
                .andExpect(jsonPath("$.code").value(200));

        mockMvc.perform(get("/api/agent-config/skills/del-skill"))
                .andDo(print())
                .andExpect(jsonPath("$.code").value(404));
    }

    // ────────────────────────────────────────────────────────
    // Test-S8: Skill 名称格式校验
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("Skill 名称含特殊字符应返回错误")
    void createSkill_invalidName_shouldFail() throws Exception {
        SkillRequest req = buildSkillRequest("invalid name!", "Invalid name test");

        mockMvc.perform(post("/api/agent-config/skills")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andDo(print())
                .andExpect(jsonPath("$.code").value(400));
    }

    // ────────────────────────────────────────────────────────
    // Helper
    // ────────────────────────────────────────────────────────

    private SkillRequest buildSkillRequest(String name, String description) {
        SkillRequest req = new SkillRequest();
        req.setName(name);
        req.setDescription(description);
        req.setContent(String.format("""
                ---
                name: %s
                description: %s
                ---
                # %s

                This is the skill body for %s.
                """, name, description, name, name));
        return req;
    }
}
