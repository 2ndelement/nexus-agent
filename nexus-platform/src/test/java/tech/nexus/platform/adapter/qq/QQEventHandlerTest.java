package tech.nexus.platform.adapter.qq;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import tech.nexus.platform.adapter.qq.handler.QQEventHandler;
import tech.nexus.platform.common.model.PlatformMessage;
import tech.nexus.platform.common.mq.PlatformMessagePublisher;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

/**
 * QQEventHandler 单元测试
 */
@ExtendWith(MockitoExtension.class)
class QQEventHandlerTest {

    @Mock
    private PlatformMessagePublisher messagePublisher;

    @InjectMocks
    private QQEventHandler eventHandler;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @BeforeEach
    void setUp() {
        // 通过反射注入 ObjectMapper
        try {
            var field = QQEventHandler.class.getDeclaredField("objectMapper");
            field.setAccessible(true);
            field.set(eventHandler, objectMapper);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    @Test
    void testHandleGroupAtMessage() throws Exception {
        String eventData = """
                {
                  "id": "test-msg-001",
                  "group_openid": "group-xyz-123",
                  "content": "<@!123456789> 帮我写一首诗",
                  "author": {
                    "member_openid": "user-openid-abc"
                  }
                }
                """;

        var node = objectMapper.readTree(eventData);
        eventHandler.handleEvent("GROUP_AT_MESSAGE_CREATE", node);

        ArgumentCaptor<PlatformMessage> captor = ArgumentCaptor.forClass(PlatformMessage.class);
        verify(messagePublisher, times(1)).publishInboundMessage(captor.capture());

        PlatformMessage captured = captor.getValue();
        assertThat(captured.getPlatform()).isEqualTo(PlatformMessage.PlatformType.QQ_GROUP);
        assertThat(captured.getChatType()).isEqualTo(PlatformMessage.ChatType.GROUP);
        assertThat(captured.getChatId()).isEqualTo("group-xyz-123");
        assertThat(captured.getSenderId()).isEqualTo("user-openid-abc");
        // @ 前缀应被清理
        assertThat(captured.getContent()).doesNotContain("<@!");
        assertThat(captured.getContent()).contains("帮我写一首诗");
    }

    @Test
    void testHandleC2CMessage() throws Exception {
        String eventData = """
                {
                  "id": "c2c-msg-001",
                  "content": "你好",
                  "author": {
                    "user_openid": "c2c-user-openid-xyz"
                  }
                }
                """;

        var node = objectMapper.readTree(eventData);
        eventHandler.handleEvent("C2C_MESSAGE_CREATE", node);

        ArgumentCaptor<PlatformMessage> captor = ArgumentCaptor.forClass(PlatformMessage.class);
        verify(messagePublisher).publishInboundMessage(captor.capture());

        PlatformMessage captured = captor.getValue();
        assertThat(captured.getPlatform()).isEqualTo(PlatformMessage.PlatformType.QQ);
        assertThat(captured.getChatType()).isEqualTo(PlatformMessage.ChatType.PRIVATE);
        assertThat(captured.getSenderId()).isEqualTo("c2c-user-openid-xyz");
        assertThat(captured.getContent()).isEqualTo("你好");
    }

    @Test
    void testHandleDirectMessage() throws Exception {
        String eventData = """
                {
                  "id": "dm-msg-001",
                  "guild_id": "guild-123",
                  "content": "频道私信内容",
                  "author": {
                    "id": "author-id-001",
                    "username": "测试用户"
                  }
                }
                """;

        var node = objectMapper.readTree(eventData);
        eventHandler.handleEvent("DIRECT_MESSAGE_CREATE", node);

        ArgumentCaptor<PlatformMessage> captor = ArgumentCaptor.forClass(PlatformMessage.class);
        verify(messagePublisher).publishInboundMessage(captor.capture());

        PlatformMessage captured = captor.getValue();
        assertThat(captured.getPlatform()).isEqualTo(PlatformMessage.PlatformType.QQ_GUILD_DM);
        assertThat(captured.getChatType()).isEqualTo(PlatformMessage.ChatType.PRIVATE);
        assertThat(captured.getChatId()).isEqualTo("guild-123");
        assertThat(captured.getContent()).isEqualTo("频道私信内容");
    }

    @Test
    void testHandleAtMessageCreate() throws Exception {
        String eventData = """
                {
                  "id": "at-msg-001",
                  "channel_id": "channel-456",
                  "guild_id": "guild-789",
                  "content": "<@!99999> 频道消息",
                  "author": {
                    "id": "freq-author-001",
                    "username": "频道用户"
                  }
                }
                """;

        var node = objectMapper.readTree(eventData);
        eventHandler.handleEvent("AT_MESSAGE_CREATE", node);

        ArgumentCaptor<PlatformMessage> captor = ArgumentCaptor.forClass(PlatformMessage.class);
        verify(messagePublisher).publishInboundMessage(captor.capture());

        PlatformMessage captured = captor.getValue();
        assertThat(captured.getPlatform()).isEqualTo(PlatformMessage.PlatformType.QQ_GUILD);
        assertThat(captured.getChatId()).isEqualTo("channel-456");
        assertThat(captured.getContent()).doesNotContain("<@!");
        assertThat(captured.getContent()).contains("频道消息");
    }

    @Test
    void testUnknownEventTypeIgnored() throws Exception {
        String eventData = "{}";
        var node = objectMapper.readTree(eventData);
        eventHandler.handleEvent("UNKNOWN_EVENT_TYPE", node);
        // 未知事件不发布消息
        verify(messagePublisher, never()).publishInboundMessage(any());
    }

    @Test
    void testAtContentCleaning() throws Exception {
        // 测试 @机器人 格式清理：<@!123456>、<@123456>
        String eventData = """
                {
                  "id": "clean-test-001",
                  "group_openid": "group-clean-001",
                  "content": "<@!100000001> <@123456> 这是真正的内容",
                  "author": {
                    "member_openid": "user-clean-001"
                  }
                }
                """;

        var node = objectMapper.readTree(eventData);
        eventHandler.handleEvent("GROUP_AT_MESSAGE_CREATE", node);

        ArgumentCaptor<PlatformMessage> captor = ArgumentCaptor.forClass(PlatformMessage.class);
        verify(messagePublisher).publishInboundMessage(captor.capture());

        String content = captor.getValue().getContent();
        assertThat(content).doesNotContain("<@!");
        assertThat(content).doesNotContain("<@");
        assertThat(content).contains("这是真正的内容");
    }
}
