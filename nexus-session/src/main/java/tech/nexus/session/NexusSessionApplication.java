package tech.nexus.session;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.ComponentScan;

/**
 * nexus-session 会话管理服务启动类。
 */
@SpringBootApplication
@ComponentScan(basePackages = {"tech.nexus.session", "tech.nexus.common"})
@MapperScan("tech.nexus.session.mapper")
public class NexusSessionApplication {

    public static void main(String[] args) {
        SpringApplication.run(NexusSessionApplication.class, args);
    }
}
