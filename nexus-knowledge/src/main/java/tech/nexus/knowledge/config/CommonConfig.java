package tech.nexus.knowledge.config;

import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.annotation.Configuration;

/**
 * 引入 nexus-common 的 GlobalExceptionHandler。
 */
@Configuration
@ComponentScan(basePackages = "tech.nexus.common.exception")
public class CommonConfig {
}
