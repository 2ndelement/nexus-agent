package tech.nexus.billing;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * NexusBilling 计费服务启动类
 */
@SpringBootApplication
@EnableScheduling
public class NexusBillingApplication {

    public static void main(String[] args) {
        SpringApplication.run(NexusBillingApplication.class, args);
    }
}
