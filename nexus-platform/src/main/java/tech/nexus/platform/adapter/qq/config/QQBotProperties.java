package tech.nexus.platform.adapter.qq.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * QQ 机器人配置属性
 * 从环境变量或 application.yml 读取
 */
@Data
@Component
@ConfigurationProperties(prefix = "nexus.platform.qq")
public class QQBotProperties {

    /**
     * 是否启用 QQ 机器人适配器
     */
    private boolean enabled = false;

    /**
     * QQ 机器人 AppID
     */
    private String appId;

    /**
     * QQ 机器人 AppSecret
     */
    private String appSecret;

    /**
     * 事件订阅 intents
     * 33554432 = GROUP_AND_C2C_EVENT (群聊+单聊)
     * 4096     = DIRECT_MESSAGE (频道私信)
     * 33558528 = 两者合并
     */
    private int intents = 33558528;

    /**
     * WebSocket Gateway URL
     */
    private String gatewayUrl = "wss://api.sgroup.qq.com/websocket/";

    /**
     * QQ API 基础 URL
     */
    private String apiBaseUrl = "https://api.sgroup.qq.com";

    /**
     * AccessToken 获取 URL
     */
    private String tokenUrl = "https://bots.qq.com/app/getAppAccessToken";

    /**
     * 心跳比例（heartbeat_interval * ratio 作为实际心跳间隔）
     */
    private double heartbeatRatio = 0.9;

    /**
     * 断线重连间隔（秒）
     */
    private int reconnectInterval = 5;

    /**
     * AccessToken 提前刷新时间（秒）
     */
    private int tokenRefreshAdvance = 300;
}
