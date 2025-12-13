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
import tech.nexus.session.dto.AppendMessageRequest;
import tech.nexus.session.dto.CreateConversationRequest;
import tech.nexus.session.entity.Conversation;
import tech.nexus.session.service.impl.ConversationServiceImpl;
import tech.nexus.session.service.impl.MessageServiceImpl;

import static org.hamcrest.Matchers.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doReturn;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * MessageController MockMvc 集成测试。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
@DisplayName("MessageController MockMvc 测试")
class MessageControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private ConversationServiceImpl conversationService;

    @Autowired
    private MessageServiceImpl messageService;

    @MockBean
    private StringRedisTemplate redisTemplate;

    private String convId;

    private String msgUrl(String convId) {
        return "/api/session/conversations/" + convId + "/messages";
    }

    @BeforeEach
    void setUp() {
        doReturn(true).when(redisTemplate).delete(anyString());

        Conversation conv = conversationService.create(1L, 100L, new CreateConversationRequest());
        convId = conv.getId();
    }

    // ─── POST 追加消息 ────────────────────────────────────────────────────────

    @Test
    @DisplayName("POST /messages → 追加成功，返回消息ID")
    void append_returns_200_with_message_id() throws Exception {
        AppendMessageRequest req = new AppendMessageRequest();
        req.setRole("user");
        req.setContent("Hello, nexus!");

        mockMvc.perform(post(msgUrl(convId))
                        .header("X-Tenant-Id", "1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.id").isNotEmpty())
                .andExpect(jsonPath("$.data.role").value("user"))
                .andExpect(jsonPath("$.data.content").value("Hello, nexus!"));
    }

    @Test
    @DisplayName("POST /messages role 为空 → code=400")
    void append_blank_role_returns_400() throws Exception {
        AppendMessageRequest req = new AppendMessageRequest();
        req.setRole("");  // 空 role，@NotBlank 失败
        req.setContent("some content");

        mockMvc.perform(post(msgUrl(convId))
                        .header("X-Tenant-Id", "1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(400));
    }

    @Test
    @DisplayName("POST /messages content 为空 → code=400")
    void append_blank_content_returns_400() throws Exception {
        AppendMessageRequest req = new AppendMessageRequest();
        req.setRole("user");
        req.setContent(""); // 空 content，@NotBlank 失败

        mockMvc.perform(post(msgUrl(convId))
                        .header("X-Tenant-Id", "1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(400));
    }

    @Test
    @DisplayName("POST /messages 会话不存在 → code=404")
    void append_nonexistent_conv_returns_404() throws Exception {
        AppendMessageRequest req = new AppendMessageRequest();
        req.setRole("user");
        req.setContent("消息");

        mockMvc.perform(post(msgUrl("non-existent-conv"))
                        .header("X-Tenant-Id", "1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(404));
    }

    // ─── GET 消息列表 ─────────────────────────────────────────────────────────

    @Test
    @DisplayName("GET /messages → 返回分页消息列表")
    void list_messages_returns_paged_result() throws Exception {
        // 预先追加 3 条消息
        for (int i = 1; i <= 3; i++) {
            AppendMessageRequest req = new AppendMessageRequest();
            req.setRole("user");
            req.setContent("消息" + i);
            messageService.appendMessage(1L, convId, req);
        }

        mockMvc.perform(get(msgUrl(convId))
                        .header("X-Tenant-Id", "1")
                        .param("page", "1")
                        .param("size", "10"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.records", hasSize(3)))
                .andExpect(jsonPath("$.data.total").value(3));
    }

    @Test
    @DisplayName("GET /messages 空会话 → 返回空列表")
    void list_messages_empty_conv_returns_empty_list() throws Exception {
        mockMvc.perform(get(msgUrl(convId))
                        .header("X-Tenant-Id", "1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.records", hasSize(0)))
                .andExpect(jsonPath("$.data.total").value(0));
    }

    // ─── DELETE 清空消息 ──────────────────────────────────────────────────────

    @Test
    @DisplayName("DELETE /messages → 清空成功，code=200")
    void clear_messages_returns_200() throws Exception {
        AppendMessageRequest req = new AppendMessageRequest();
        req.setRole("user");
        req.setContent("待清空消息");
        messageService.appendMessage(1L, convId, req);

        mockMvc.perform(delete(msgUrl(convId))
                        .header("X-Tenant-Id", "1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));
    }

    @Test
    @DisplayName("DELETE /messages 不存在的 convId → code=404")
    void clear_nonexistent_conv_returns_404() throws Exception {
        mockMvc.perform(delete(msgUrl("non-existent-conv"))
                        .header("X-Tenant-Id", "1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(404));
    }
}
