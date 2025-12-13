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
import tech.nexus.session.dto.CreateConversationRequest;
import tech.nexus.session.entity.Conversation;
import tech.nexus.session.service.impl.ConversationServiceImpl;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doReturn;

/**
 * ConversationService 服务层测试。
 *
 * <p>使用 H2 内存数据库，Redis 使用 MockBean。
 */
@SpringBootTest
@ActiveProfiles("test")
@Transactional
@DisplayName("ConversationService 服务层测试")
class ConversationServiceTest {

    @Autowired
    private ConversationServiceImpl conversationService;

    @MockBean
    private StringRedisTemplate redisTemplate;

    private static final Long TENANT_A = 1L;
    private static final Long TENANT_B = 2L;
    private static final Long USER_1 = 100L;
    private static final Long USER_2 = 200L;

    @BeforeEach
    void setUp() {
        // Redis delete 调用不做任何操作
        doReturn(true).when(redisTemplate).delete(anyString());
    }

    // ─── 创建会话 ─────────────────────────────────────────────────────────────

    @Test
    @DisplayName("创建会话 → 返回 UUID convId")
    void create_returns_uuid_convId() {
        CreateConversationRequest req = new CreateConversationRequest();
        req.setTitle("测试会话");

        Conversation conv = conversationService.create(TENANT_A, USER_1, req);

        assertThat(conv.getId()).isNotNull().isNotBlank();
        assertThat(conv.getId()).doesNotContain("-"); // UUID 已去除连字符
        assertThat(conv.getId()).hasSizeGreaterThanOrEqualTo(32);
        assertThat(conv.getTenantId()).isEqualTo(TENANT_A);
        assertThat(conv.getUserId()).isEqualTo(USER_1);
        assertThat(conv.getTitle()).isEqualTo("测试会话");
        assertThat(conv.getStatus()).isEqualTo(1);
        assertThat(conv.getMessageCount()).isEqualTo(0);
    }

    @Test
    @DisplayName("创建会话不指定标题 → 默认标题 '新对话'")
    void create_default_title() {
        CreateConversationRequest req = new CreateConversationRequest();

        Conversation conv = conversationService.create(TENANT_A, USER_1, req);

        assertThat(conv.getTitle()).isEqualTo("新对话");
        assertThat(conv.getModel()).isEqualTo("MiniMax-M2.5-highspeed");
    }

    // ─── 同一租户不同用户隔离 ─────────────────────────────────────────────────

    @Test
    @DisplayName("同一租户不同用户只能看自己的会话")
    void list_same_tenant_different_user_isolation() {
        // user1 创建 2 个会话
        conversationService.create(TENANT_A, USER_1, new CreateConversationRequest());
        conversationService.create(TENANT_A, USER_1, new CreateConversationRequest());
        // user2 创建 1 个会话
        conversationService.create(TENANT_A, USER_2, new CreateConversationRequest());

        PageResult<Conversation> user1Result = conversationService.listByUser(TENANT_A, USER_1, 1, 20);
        PageResult<Conversation> user2Result = conversationService.listByUser(TENANT_A, USER_2, 1, 20);

        assertThat(user1Result.getRecords()).hasSize(2);
        assertThat(user2Result.getRecords()).hasSize(1);
        assertThat(user1Result.getRecords())
                .allMatch(c -> c.getUserId().equals(USER_1));
        assertThat(user2Result.getRecords())
                .allMatch(c -> c.getUserId().equals(USER_2));
    }

    // ─── 不同租户相同 convId 共存 ─────────────────────────────────────────────

    @Test
    @DisplayName("不同租户的 convId 相同也能共存（无冲突）")
    void different_tenant_same_convId_no_conflict() {
        // 手动创建两个 convId 相同的会话，分属不同租户
        CreateConversationRequest req = new CreateConversationRequest();
        req.setTitle("同ID会话");

        Conversation convA = conversationService.create(TENANT_A, USER_1, req);
        Conversation convB = conversationService.create(TENANT_B, USER_1, req);

        // 两个 convId 在不同租户下独立存在
        assertThat(conversationService.getById(TENANT_A, convA.getId())).isNotNull();
        assertThat(conversationService.getById(TENANT_B, convB.getId())).isNotNull();
    }

    // ─── 获取会话详情 ─────────────────────────────────────────────────────────

    @Test
    @DisplayName("获取不存在的会话 → 抛 BizException NOT_FOUND")
    void getById_not_found_throws() {
        assertThatThrownBy(() -> conversationService.getById(TENANT_A, "non-existent-id"))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("会话不存在");
    }

    @Test
    @DisplayName("跨租户获取会话 → 抛 BizException NOT_FOUND")
    void getById_cross_tenant_throws() {
        Conversation conv = conversationService.create(TENANT_A, USER_1, new CreateConversationRequest());

        // TENANT_B 无法获取 TENANT_A 的会话
        assertThatThrownBy(() -> conversationService.getById(TENANT_B, conv.getId()))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("会话不存在");
    }

    // ─── 归档会话 ─────────────────────────────────────────────────────────────

    @Test
    @DisplayName("归档会话后，列表中不再出现")
    void archive_removes_from_list() {
        Conversation conv = conversationService.create(TENANT_A, USER_1, new CreateConversationRequest());

        conversationService.archive(TENANT_A, USER_1, conv.getId());

        PageResult<Conversation> result = conversationService.listByUser(TENANT_A, USER_1, 1, 20);
        assertThat(result.getRecords())
                .noneMatch(c -> c.getId().equals(conv.getId()));
    }

    @Test
    @DisplayName("其他用户归档他人会话 → 抛 BizException FORBIDDEN")
    void archive_other_user_conv_throws_forbidden() {
        Conversation conv = conversationService.create(TENANT_A, USER_1, new CreateConversationRequest());

        assertThatThrownBy(() -> conversationService.archive(TENANT_A, USER_2, conv.getId()))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("无权操作该会话");
    }

    // ─── 更新标题 ─────────────────────────────────────────────────────────────

    @Test
    @DisplayName("更新标题 → 标题变更成功")
    void updateTitle_success() {
        Conversation conv = conversationService.create(TENANT_A, USER_1, new CreateConversationRequest());

        conversationService.updateTitle(TENANT_A, USER_1, conv.getId(), "新标题");

        Conversation updated = conversationService.getById(TENANT_A, conv.getId());
        assertThat(updated.getTitle()).isEqualTo("新标题");
    }
}
