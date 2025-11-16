package tech.nexus.auth.config;

import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.annotation.Configuration;

/**
 * 将 nexus-common 的 GlobalExceptionHandler 扫描进来。
 */
@Configuration
@ComponentScan(basePackages = "tech.nexus.common.exception")
public class CommonConfig {
}
