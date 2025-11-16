package tech.nexus.auth;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("tech.nexus.auth.mapper")
public class NexusAuthApplication {

    public static void main(String[] args) {
        SpringApplication.run(NexusAuthApplication.class, args);
    }
}
