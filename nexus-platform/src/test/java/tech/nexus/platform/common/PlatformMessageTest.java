package tech.nexus.platform.common;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import tech.nexus.platform.common.model.PlatformMessage;

import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * PlatformMessage 模型单元测试
 */
class PlatformMessageTest {

    private final ObjectMapper objectMapper = new ObjectMapper()
            .findAndRegisterModules();

    @Test
    void testBuildWebChatMessage() {
        PlatformMessage message = PlatformMessage.builder()
                .messageId("msg-001")
                .platform(PlatformMessage.PlatformType.WEBCHAT)
                .messageType(PlatformMessage.MessageType.TEXT)
                .chatType(PlatformMessage.ChatType.PRIVATE)
                .senderId("user-123")
                .content("Hello World")
                .tenantId("tenant-001")
                .receivedAt(LocalDateTime.now())
                .build();

        assertThat(message.getMessageId()).isEqualTo("msg-001");
        assertThat(message.getPlatform()).isEqualTo(PlatformMessage.PlatformType.WEBCHAT);
        assertThat(message.getMessageType()).isEqualTo(PlatformMessage.MessageType.TEXT);
        assertThat(message.getChatType()).isEqualTo(PlatformMessage.ChatType.PRIVATE);
        assertThat(message.getSenderId()).isEqualTo("user-123");
        assertThat(message.getContent()).isEqualTo("Hello World");
        assertThat(message.getTenantId()).isEqualTo("tenant-001");
    }

    @Test
    void testBuildQQGroupMessage() {
        PlatformMessage message = PlatformMessage.builder()
                .messageId("qq-msg-001")
                .platform(PlatformMessage.PlatformType.QQ_GROUP)
                .messageType(PlatformMessage.MessageType.AT)
                .chatType(PlatformMessage.ChatType.GROUP)
                .senderId("openid-abc")
                .chatId("group-openid-xyz")
                .content("帮我查一下天气")
                .receivedAt(LocalDateTime.now())
                .build();

        assertThat(message.getPlatform()).isEqualTo(PlatformMessage.PlatformType.QQ_GROUP);
        assertThat(message.getChatType()).isEqualTo(PlatformMessage.ChatType.GROUP);
        assertThat(message.getChatId()).isEqualTo("group-openid-xyz");
    }

    @Test
    void testMessageSerialization() throws Exception {
        PlatformMessage message = PlatformMessage.builder()
                .messageId("test-id")
                .platform(PlatformMessage.PlatformType.QQ)
                .messageType(PlatformMessage.MessageType.TEXT)
                .chatType(PlatformMessage.ChatType.PRIVATE)
                .senderId("user-456")
                .content("测试消息")
                .receivedAt(LocalDateTime.of(2026, 3, 17, 10, 0, 0))
                .build();

        String json = objectMapper.writeValueAsString(message);
        assertThat(json).contains("\"messageId\":\"test-id\"");
        assertThat(json).contains("\"platform\":\"QQ\"");
        assertThat(json).contains("\"content\":\"测试消息\"");
    }

    @Test
    void testMessageDeserialization() throws Exception {
        String json = """
                {
                  "messageId": "deser-001",
                  "platform": "WEBCHAT",
                  "messageType": "TEXT",
                  "chatType": "PRIVATE",
                  "senderId": "user-789",
                  "content": "反序列化测试",
                  "tenantId": "tenant-002"
                }
                """;

        PlatformMessage message = objectMapper.readValue(json, PlatformMessage.class);
        assertThat(message.getMessageId()).isEqualTo("deser-001");
        assertThat(message.getPlatform()).isEqualTo(PlatformMessage.PlatformType.WEBCHAT);
        assertThat(message.getContent()).isEqualTo("反序列化测试");
        assertThat(message.getTenantId()).isEqualTo("tenant-002");
    }

    @Test
    void testAllPlatformTypes() {
        for (PlatformMessage.PlatformType type : PlatformMessage.PlatformType.values()) {
            PlatformMessage msg = PlatformMessage.builder()
                    .platform(type)
                    .content("test")
                    .build();
            assertThat(msg.getPlatform()).isEqualTo(type);
        }
    }

    @Test
    void testDefaultValues() {
        PlatformMessage message = new PlatformMessage();
        assertThat(message.getMessageId()).isNull();
        assertThat(message.getContent()).isNull();
        assertThat(message.getTenantId()).isNull();
    }
}
