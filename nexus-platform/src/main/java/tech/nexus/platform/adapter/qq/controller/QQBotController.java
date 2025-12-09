package tech.nexus.platform.adapter.qq.controller;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import tech.nexus.platform.adapter.qq.client.QQGatewayClient;
import tech.nexus.platform.adapter.qq.config.QQBotProperties;
import tech.nexus.platform.adapter.qq.service.QQMessageService;
import tech.nexus.platform.adapter.qq.service.QQTokenService;

import java.util.Map;

/**
 * QQ 机器人管理 REST Controller
 * 提供状态查询和手动操作接口
 */
@Slf4j
@RestController
@RequestMapping("/api/platform/qq")
@RequiredArgsConstructor
public class QQBotController {

    private final QQBotProperties properties;
    private final QQGatewayClient gatewayClient;
    private final QQTokenService tokenService;
    private final QQMessageService messageService;

    /**
     * 获取适配器状态
     */
    @GetMapping("/status")
    public ResponseEntity<Map<String, Object>> status() {
        return ResponseEntity.ok(Map.of(
                "adapter", "qq",
                "enabled", properties.isEnabled(),
                "connected", gatewayClient.isConnected(),
                "appId", properties.getAppId() != null ? properties.getAppId() : "未配置",
                "intents", properties.getIntents(),
                "tokenValid", tokenService.isTokenValid()
        ));
    }

    /**
     * 手动重连 Gateway
     */
    @PostMapping("/reconnect")
    public ResponseEntity<Map<String, Object>> reconnect() {
        if (!properties.isEnabled()) {
            return ResponseEntity.badRequest().body(Map.of("error", "QQ适配器未启用"));
        }
        log.info("[QQBot] 手动触发重连");
        gatewayClient.connect();
        return ResponseEntity.ok(Map.of("status", "reconnecting"));
    }

    /**
     * 手动刷新 AccessToken
     */
    @PostMapping("/token/refresh")
    public ResponseEntity<Map<String, Object>> refreshToken() {
        if (!properties.isEnabled()) {
            return ResponseEntity.badRequest().body(Map.of("error", "QQ适配器未启用"));
        }
        try {
            tokenService.refreshToken();
            return ResponseEntity.ok(Map.of(
                    "status", "ok",
                    "tokenValid", tokenService.isTokenValid(),
                    "expireAt", tokenService.getTokenExpireTime().toString()
            ));
        } catch (Exception e) {
            return ResponseEntity.internalServerError().body(Map.of("error", e.getMessage()));
        }
    }

    /**
     * 发送测试消息（仅开发调试用）
     */
    @PostMapping("/test/send")
    public ResponseEntity<Map<String, Object>> sendTestMessage(
            @RequestParam String type,
            @RequestParam String targetId,
            @RequestParam String content) {
        if (!properties.isEnabled()) {
            return ResponseEntity.badRequest().body(Map.of("error", "QQ适配器未启用"));
        }

        boolean success = switch (type) {
            case "c2c" -> messageService.sendC2CMessage(targetId, content, null);
            case "group" -> messageService.sendGroupMessage(targetId, content, null);
            case "channel" -> messageService.sendChannelMessage(targetId, content, null);
            case "dm" -> messageService.sendDirectMessage(targetId, content, null);
            default -> {
                log.warn("[QQBot] 未知消息类型: {}", type);
                yield false;
            }
        };

        return ResponseEntity.ok(Map.of("success", success, "type", type, "targetId", targetId));
    }
}
