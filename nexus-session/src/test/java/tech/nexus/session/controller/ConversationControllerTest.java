package tech.nexus.session.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;
import tech.nexus.session.dto.CreateConversationRequest;
import tech.nexus.session.dto.UpdateTitleRequest;
import tech.nexus.session.entity.Conversation;
import tech.nexus.session.service.impl.ConversationServiceImpl;

import static org.hamcrest.Matchers.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doReturn;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * ConversationController MockMvc 集成测试。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
@DisplayName("ConversationController MockMvc 测试")
class ConversationControllerTest {

    private static final String BASE_URL = "/api/session/conversations";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private ConversationServiceImpl conversationService;

    @MockBean
    private StringRedisTemplate redisTemplate;

    @BeforeEach
    void setUp() {
        doReturn(true).when(redisTemplate).delete(anyString());
    }

    // ─── POST /api/session/conversations ─────────────────────────────────────

    @Test
    @DisplayName("POST /conversations → 201 + convId")
    void create_returns_200_with_convId() throws Exception {
        CreateConversationRequest req = new CreateConversationRequest();
        req.setTitle("控制器测试会话");

        mockMvc.perform(post(BASE_URL)
                        .header("X-Tenant-Id", "1")
                        .header("X-User-Id", "100")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.id").isNotEmpty())
                .andExpect(jsonPath("$.data.title").value("控制器测试会话"))
                .andExpect(jsonPath("$.data.status").value(1));
    }

    @Test
    @DisplayName("POST /conversations（无 Body）→ 默认标题 '新对话'")
    void create_no_body_default_title() throws Exception {
        mockMvc.perform(post(BASE_URL)
                        .header("X-Tenant-Id", "1")
                        .header("X-User-Id", "100")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.title").value("新对话"));
    }

    // ─── GET /api/session/conversations ──────────────────────────────────────

    @Test
    @DisplayName("GET /conversations → 返回分页列表")
    void list_returns_paged_result() throws Exception {
        conversationService.create(1L, 100L, new CreateConversationRequest());
        conversationService.create(1L, 100L, new CreateConversationRequest());

        mockMvc.perform(get(BASE_URL)
                        .header("X-Tenant-Id", "1")
                        .header("X-User-Id", "100")
                        .param("page", "1")
                        .param("size", "10"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.records", hasSize(2)))
                .andExpect(jsonPath("$.data.total").value(2));
    }

    // ─── GET /api/session/conversations/{id} ─────────────────────────────────

    @Test
    @DisplayName("GET /conversations/{id} → 返回会话详情")
    void getById_returns_detail() throws Exception {
        Conversation conv = conversationService.create(1L, 100L, new CreateConversationRequest());

        mockMvc.perform(get(BASE_URL + "/" + conv.getId())
                        .header("X-Tenant-Id", "1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.id").value(conv.getId()));
    }

    @Test
    @DisplayName("GET /conversations/{id} 不存在 → code=404")
    void getById_not_found_returns_error_code() throws Exception {
        mockMvc.perform(get(BASE_URL + "/non-existent")
                        .header("X-Tenant-Id", "1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(404));
    }

    // ─── DELETE /api/session/conversations/{id} ───────────────────────────────

    @Test
    @DisplayName("DELETE /conversations/{id} → 归档成功，code=200")
    void archive_returns_200() throws Exception {
        Conversation conv = conversationService.create(1L, 100L, new CreateConversationRequest());

        mockMvc.perform(delete(BASE_URL + "/" + conv.getId())
                        .header("X-Tenant-Id", "1")
                        .header("X-User-Id", "100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));
    }

    @Test
    @DisplayName("DELETE /conversations/{id} 他人会话 → code=403")
    void archive_other_user_returns_403() throws Exception {
        Conversation conv = conversationService.create(1L, 100L, new CreateConversationRequest());

        mockMvc.perform(delete(BASE_URL + "/" + conv.getId())
                        .header("X-Tenant-Id", "1")
                        .header("X-User-Id", "200"))   // 另一个用户
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(403));
    }

    // ─── PUT /api/session/conversations/{id}/title ───────────────────────────

    @Test
    @DisplayName("PUT /conversations/{id}/title → 更新成功，code=200")
    void updateTitle_returns_200() throws Exception {
        Conversation conv = conversationService.create(1L, 100L, new CreateConversationRequest());

        UpdateTitleRequest req = new UpdateTitleRequest();
        req.setTitle("新标题");

        mockMvc.perform(put(BASE_URL + "/" + conv.getId() + "/title")
                        .header("X-Tenant-Id", "1")
                        .header("X-User-Id", "100")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));
    }

    @Test
    @DisplayName("PUT /conversations/{id}/title 空标题 → 参数错误，code=400")
    void updateTitle_blank_title_returns_400() throws Exception {
        Conversation conv = conversationService.create(1L, 100L, new CreateConversationRequest());

        UpdateTitleRequest req = new UpdateTitleRequest();
        req.setTitle(""); // 空标题，@NotBlank 校验失败

        mockMvc.perform(put(BASE_URL + "/" + conv.getId() + "/title")
                        .header("X-Tenant-Id", "1")
                        .header("X-User-Id", "100")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(400));
    }
}
