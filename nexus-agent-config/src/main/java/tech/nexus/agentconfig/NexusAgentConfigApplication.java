package tech.nexus.agentconfig;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * nexus-agent-config 服务启动类（端口 8006）。
 */
@SpringBootApplication(scanBasePackages = {"tech.nexus.agentconfig", "tech.nexus.common"})
@MapperScan("tech.nexus.agentconfig.mapper")
public class NexusAgentConfigApplication {

    public static void main(String[] args) {
        SpringApplication.run(NexusAgentConfigApplication.class, args);
    }
}
