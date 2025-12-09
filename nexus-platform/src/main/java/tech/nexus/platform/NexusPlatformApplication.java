package tech.nexus.platform;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * NexusPlatform 平台适配服务启动类
 * 端口: 8005
 * 职责: WebChat WebSocket 适配器 & QQ 机器人适配器
 */
@SpringBootApplication
@EnableScheduling
@ConfigurationPropertiesScan
public class NexusPlatformApplication {

    public static void main(String[] args) {
        SpringApplication.run(NexusPlatformApplication.class, args);
    }
}
