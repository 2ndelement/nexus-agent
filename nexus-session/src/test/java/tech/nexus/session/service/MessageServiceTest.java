package tech.nexus.session.service;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.PageResult;
import tech.nexus.session.dto.AppendMessageRequest;
import tech.nexus.session.dto.CreateConversationRequest;
import tech.nexus.session.entity.Conversation;
import tech.nexus.session.entity.Message;
import tech.nexus.session.service.impl.ConversationServiceImpl;
import tech.nexus.session.service.impl.MessageServiceImpl;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doReturn;

/**
 * MessageService 服务层测试。
 *
 * <p>使用 H2 内存数据库，Redis 使用 MockBean。
 */
@SpringBootTest
@ActiveProfiles("test")
@Transactional
@DisplayName("MessageService 服务层测试")
class MessageServiceTest {

    @Autowired
    private MessageServiceImpl messageService;

    @Autowired
    private ConversationServiceImpl conversationService;

    @MockBean
    private StringRedisTemplate redisTemplate;

    private static final Long TENANT_A = 1L;
    private static final Long TENANT_B = 2L;
    private static final Long USER_1 = 100L;

    private String convIdA;
    private String convIdB;

    @BeforeEach
    void setUp() {
        doReturn(true).when(redisTemplate).delete(anyString());

        // 每次测试前为 TENANT_A 和 TENANT_B 各创建一个会话
        Conversation convA = conversationService.create(TENANT_A, USER_1, new CreateConversationRequest());
        convIdA = convA.getId();

        Conversation convB = conversationService.create(TENANT_B, USER_1, new CreateConversationRequest());
        convIdB = convB.getId();
    }

    // ─── 追加消息 ─────────────────────────────────────────────────────────────

    @Test
    @DisplayName("追加消息 → 消息 ID 自增，角色/内容正确")
    void append_returns_saved_message() {
        AppendMessageRequest req = new AppendMessageRequest();
        req.setRole("user");
        req.setContent("你好，世界");
        req.setTokens(5);

        Message msg = messageService.appendMessage(TENANT_A, convIdA, req);

        assertThat(msg.getId()).isNotNull().isPositive();
        assertThat(msg.getRole()).isEqualTo("user");
        assertThat(msg.getContent()).isEqualTo("你好，世界");
        assertThat(msg.getTokens()).isEqualTo(5);
        assertThat(msg.getTenantId()).isEqualTo(TENANT_A);
        assertThat(msg.getConversationId()).isEqualTo(convIdA);
    }

    @Test
    @DisplayName("追加消息 → 会话消息计数增加")
    void append_increments_message_count() {
        AppendMessageRequest req = new AppendMessageRequest();
        req.setRole("user");
        req.setContent("消息1");

        messageService.appendMessage(TENANT_A, convIdA, req);
        messageService.appendMessage(TENANT_A, convIdA, req);

        Conversation conv = conversationService.getById(TENANT_A, convIdA);
        assertThat(conv.getMessageCount()).isEqualTo(2);
    }

    // ─── 幂等性 ───────────────────────────────────────────────────────────────

    @Test
    @DisplayName("相同 idempotentKey 重复提交 → 返回已有消息，不重复写入")
    void append_idempotent_duplicate_key_returns_existing() {
        AppendMessageRequest req = new AppendMessageRequest();
        req.setRole("user");
        req.setContent("幂等消息");
        req.setIdempotentKey("idem-key-001");

        Message first = messageService.appendMessage(TENANT_A, convIdA, req);
        Message second = messageService.appendMessage(TENANT_A, convIdA, req);

        // 两次返回相同的 ID
        assertThat(second.getId()).isEqualTo(first.getId());

        // 列表中只有 1 条
        PageResult<Message> result = messageService.listMessages(TENANT_A, convIdA, 1, 20);
        assertThat(result.getRecords()).hasSize(1);
    }

    @Test
    @DisplayName("不同 idempotentKey → 分别写入，两条消息独立")
    void append_different_idempotent_keys_both_saved() {
        AppendMessageRequest req1 = new AppendMessageRequest();
        req1.setRole("user");
        req1.setContent("消息A");
        req1.setIdempotentKey("key-A");

        AppendMessageRequest req2 = new AppendMessageRequest();
        req2.setRole("user");
        req2.setContent("消息B");
        req2.setIdempotentKey("key-B");

        messageService.appendMessage(TENANT_A, convIdA, req1);
        messageService.appendMessage(TENANT_A, convIdA, req2);

        PageResult<Message> result = messageService.listMessages(TENANT_A, convIdA, 1, 20);
        assertThat(result.getRecords()).hasSize(2);
    }

    // ─── 消息列表顺序 ─────────────────────────────────────────────────────────

    @Test
    @DisplayName("消息列表 → 按 create_time 升序排列")
    void list_messages_in_ascending_order() {
        for (int i = 1; i <= 3; i++) {
            AppendMessageRequest req = new AppendMessageRequest();
            req.setRole(i % 2 == 1 ? "user" : "assistant");
            req.setContent("消息" + i);
            messageService.appendMessage(TENANT_A, convIdA, req);
        }

        PageResult<Message> result = messageService.listMessages(TENANT_A, convIdA, 1, 20);
        assertThat(result.getRecords()).hasSize(3);

        // 验证升序
        for (int i = 0; i < result.getRecords().size() - 1; i++) {
            Message curr = result.getRecords().get(i);
            Message next = result.getRecords().get(i + 1);
            assertThat(curr.getId()).isLessThanOrEqualTo(next.getId());
        }
    }

    // ─── 分页 ─────────────────────────────────────────────────────────────────

    @Test
    @DisplayName("消息分页 → total 和 records 正确")
    void list_messages_pagination() {
        for (int i = 0; i < 5; i++) {
            AppendMessageRequest req = new AppendMessageRequest();
            req.setRole("user");
            req.setContent("消息" + i);
            messageService.appendMessage(TENANT_A, convIdA, req);
        }

        PageResult<Message> page1 = messageService.listMessages(TENANT_A, convIdA, 1, 2);
        PageResult<Message> page2 = messageService.listMessages(TENANT_A, convIdA, 2, 2);
        PageResult<Message> page3 = messageService.listMessages(TENANT_A, convIdA, 3, 2);

        assertThat(page1.getTotal()).isEqualTo(5L);
        assertThat(page1.getRecords()).hasSize(2);
        assertThat(page2.getRecords()).hasSize(2);
        assertThat(page3.getRecords()).hasSize(1);
    }

    // ─── 跨租户隔离 ───────────────────────────────────────────────────────────

    @Test
    @DisplayName("追加消息到不存在会话（跨租户）→ 抛 BizException NOT_FOUND")
    void append_to_nonexistent_conv_throws() {
        AppendMessageRequest req = new AppendMessageRequest();
        req.setRole("user");
        req.setContent("跨租户消息");

        // TENANT_B 使用 TENANT_A 的 convId → 会话不存在
        assertThatThrownBy(() -> messageService.appendMessage(TENANT_B, convIdA, req))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("会话不存在");
    }

    @Test
    @DisplayName("列出消息跨租户 → 抛 BizException NOT_FOUND")
    void list_messages_cross_tenant_throws() {
        assertThatThrownBy(() -> messageService.listMessages(TENANT_B, convIdA, 1, 20))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("会话不存在");
    }

    // ─── 清空消息 ─────────────────────────────────────────────────────────────

    @Test
    @DisplayName("清空消息 → 列表为空")
    void clear_messages_empties_list() {
        AppendMessageRequest req = new AppendMessageRequest();
        req.setRole("user");
        req.setContent("待清空消息");
        messageService.appendMessage(TENANT_A, convIdA, req);
        messageService.appendMessage(TENANT_A, convIdA, req);

        messageService.clearMessages(TENANT_A, convIdA);

        PageResult<Message> result = messageService.listMessages(TENANT_A, convIdA, 1, 20);
        assertThat(result.getRecords()).isEmpty();
        assertThat(result.getTotal()).isEqualTo(0L);
    }

    @Test
    @DisplayName("清空一个会话的消息不影响另一个会话")
    void clear_messages_does_not_affect_other_conv() {
        // convIdA 追加消息
        AppendMessageRequest req = new AppendMessageRequest();
        req.setRole("user");
        req.setContent("convA 消息");
        messageService.appendMessage(TENANT_A, convIdA, req);

        // convIdB（TENANT_B）追加消息
        AppendMessageRequest reqB = new AppendMessageRequest();
        reqB.setRole("user");
        reqB.setContent("convB 消息");
        messageService.appendMessage(TENANT_B, convIdB, reqB);

        // 清空 TENANT_A 的 convIdA
        messageService.clearMessages(TENANT_A, convIdA);

        // TENANT_A convIdA 已空
        PageResult<Message> resultA = messageService.listMessages(TENANT_A, convIdA, 1, 20);
        assertThat(resultA.getRecords()).isEmpty();

        // TENANT_B convIdB 不受影响
        PageResult<Message> resultB = messageService.listMessages(TENANT_B, convIdB, 1, 20);
        assertThat(resultB.getRecords()).hasSize(1);
    }
}
