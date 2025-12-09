package tech.nexus.platform.adapter.webchat.handler;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import tech.nexus.platform.common.model.PlatformMessage;
import tech.nexus.platform.common.mq.PlatformMessagePublisher;

import java.util.HashMap;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/**
 * WebChatWebSocketHandler 单元测试
 * 注意：与被测类同包，可以访问 protected 方法
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class WebChatWebSocketHandlerTest {

    @Mock
    private PlatformMessagePublisher messagePublisher;

    @Mock
    private WebSocketSession mockSession;

    private WebChatWebSocketHandler handler;

    private final ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();

    @BeforeEach
    void setUp() throws Exception {
        handler = new WebChatWebSocketHandler(objectMapper, messagePublisher);

        when(mockSession.getId()).thenReturn("test-session-001");
        when(mockSession.isOpen()).thenReturn(true);
        when(mockSession.getAttributes()).thenReturn(new HashMap<>());
    }

    @Test
    void testConnectionEstablished() throws Exception {
        handler.afterConnectionEstablished(mockSession);

        assertThat(handler.getActiveSessionCount()).isEqualTo(1);
        verify(mockSession).sendMessage(any(TextMessage.class));
    }

    @Test
    void testConnectionClosed() throws Exception {
        handler.afterConnectionEstablished(mockSession);
        assertThat(handler.getActiveSessionCount()).isEqualTo(1);

        handler.afterConnectionClosed(mockSession, CloseStatus.NORMAL);
        assertThat(handler.getActiveSessionCount()).isEqualTo(0);
    }

    @Test
    void testHandlePingMessage() throws Exception {
        handler.afterConnectionEstablished(mockSession);
        reset(mockSession);
        when(mockSession.isOpen()).thenReturn(true);
        when(mockSession.getId()).thenReturn("test-session-001");

        String pingMsg = objectMapper.writeValueAsString(Map.of("type", "ping"));
        handler.handleTextMessage(mockSession, new TextMessage(pingMsg));

        ArgumentCaptor<TextMessage> captor = ArgumentCaptor.forClass(TextMessage.class);
        verify(mockSession).sendMessage(captor.capture());
        String response = captor.getValue().getPayload();
        assertThat(response).contains("\"type\":\"pong\"");
    }

    @Test
    void testHandleChatMessage() throws Exception {
        handler.afterConnectionEstablished(mockSession);
        when(mockSession.getAttributes()).thenReturn(new HashMap<>(
                Map.of("tenantId", "tenant-001", "userId", "user-abc")
        ));

        String chatMsg = objectMapper.writeValueAsString(Map.of(
                "type", "message",
                "content", "你好，世界"
        ));
        handler.handleTextMessage(mockSession, new TextMessage(chatMsg));

        ArgumentCaptor<PlatformMessage> captor = ArgumentCaptor.forClass(PlatformMessage.class);
        verify(messagePublisher).publishInboundMessage(captor.capture());

        PlatformMessage published = captor.getValue();
        assertThat(published.getPlatform()).isEqualTo(PlatformMessage.PlatformType.WEBCHAT);
        assertThat(published.getContent()).isEqualTo("你好，世界");
        assertThat(published.getTenantId()).isEqualTo("tenant-001");
    }

    @Test
    void testHandleEmptyContentMessage() throws Exception {
        handler.afterConnectionEstablished(mockSession);
        reset(mockSession);
        when(mockSession.isOpen()).thenReturn(true);
        when(mockSession.getId()).thenReturn("test-session-001");
        when(mockSession.getAttributes()).thenReturn(new HashMap<>());

        String emptyMsg = objectMapper.writeValueAsString(Map.of(
                "type", "message",
                "content", "  "
        ));
        handler.handleTextMessage(mockSession, new TextMessage(emptyMsg));

        verify(messagePublisher, never()).publishInboundMessage(any());
        ArgumentCaptor<TextMessage> captor = ArgumentCaptor.forClass(TextMessage.class);
        verify(mockSession).sendMessage(captor.capture());
        assertThat(captor.getValue().getPayload()).contains("error");
    }

    @Test
    void testSendToNonExistentSession() throws Exception {
        handler.sendToSession("non-existent-session", "hello");
        verify(mockSession, never()).sendMessage(any());
    }

    @Test
    void testHandleIdentifyMessage() throws Exception {
        Map<String, Object> attrs = new HashMap<>();
        when(mockSession.getAttributes()).thenReturn(attrs);
        handler.afterConnectionEstablished(mockSession);
        reset(mockSession);
        when(mockSession.isOpen()).thenReturn(true);
        when(mockSession.getId()).thenReturn("test-session-001");
        when(mockSession.getAttributes()).thenReturn(attrs);

        String identifyMsg = objectMapper.writeValueAsString(Map.of(
                "type", "identify",
                "tenantId", "tenant-xyz",
                "userId", "user-456"
        ));
        handler.handleTextMessage(mockSession, new TextMessage(identifyMsg));

        assertThat(attrs.get("tenantId")).isEqualTo("tenant-xyz");
        assertThat(attrs.get("userId")).isEqualTo("user-456");

        ArgumentCaptor<TextMessage> captor = ArgumentCaptor.forClass(TextMessage.class);
        verify(mockSession).sendMessage(captor.capture());
        assertThat(captor.getValue().getPayload()).contains("identified");
    }
}
