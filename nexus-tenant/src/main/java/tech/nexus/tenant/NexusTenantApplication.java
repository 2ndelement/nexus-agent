package tech.nexus.tenant;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication(scanBasePackages = {"tech.nexus.tenant", "tech.nexus.common"})
@MapperScan("tech.nexus.tenant.mapper")
public class NexusTenantApplication {
    public static void main(String[] args) {
        SpringApplication.run(NexusTenantApplication.class, args);
    }
}
