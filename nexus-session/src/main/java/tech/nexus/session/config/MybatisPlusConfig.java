package tech.nexus.session.config;

import com.baomidou.mybatisplus.extension.plugins.MybatisPlusInterceptor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * MyBatis-Plus 配置。
 *
 * <p>MyBatis-Plus 3.5.9 中分页拦截器已迁移至 mybatis-plus-jsqlparser 模块，
 * 此处提供一个空的 MybatisPlusInterceptor bean 供 Spring 上下文使用；
 * 分页逻辑通过手动 LIMIT/OFFSET 实现（见 ConversationServiceImpl / MessageServiceImpl）。
 */
@Configuration
public class MybatisPlusConfig {

    @Bean
    public MybatisPlusInterceptor mybatisPlusInterceptor() {
        return new MybatisPlusInterceptor();
    }
}
