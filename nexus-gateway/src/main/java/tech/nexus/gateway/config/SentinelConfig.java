package tech.nexus.gateway.config;

import com.alibaba.csp.sentinel.adapter.gateway.common.SentinelGatewayConstants;
import com.alibaba.csp.sentinel.adapter.gateway.common.api.ApiDefinition;
import com.alibaba.csp.sentinel.adapter.gateway.common.api.ApiPathPredicateItem;
import com.alibaba.csp.sentinel.adapter.gateway.common.api.GatewayApiDefinitionManager;
import com.alibaba.csp.sentinel.adapter.gateway.common.rule.GatewayFlowRule;
import com.alibaba.csp.sentinel.adapter.gateway.common.rule.GatewayRuleManager;
import com.alibaba.csp.sentinel.adapter.gateway.sc.exception.SentinelGatewayBlockExceptionHandler;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.codec.ServerCodecConfigurer;
import org.springframework.web.reactive.result.view.ViewResolver;

import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Sentinel Gateway 限流配置。
 *
 * <p>限流规则设计：
 * <ul>
 *   <li>全局 API 限流：整个网关 200 QPS</li>
 *   <li>Agent 会话：50 QPS（Agent 调用 LLM 成本高）</li>
 *   <li>Auth 登录：20 QPS（防暴力破解）</li>
 *   <li>知识库上传：10 QPS（文件处理耗资源）</li>
 * </ul>
 *
 * <p>注意：此为初始规则，生产环境应通过 Sentinel Dashboard 动态调整。
 */
@Slf4j
@Configuration
public class SentinelConfig {

    private final List<ViewResolver> viewResolvers;
    private final ServerCodecConfigurer serverCodecConfigurer;

    public SentinelConfig(
            ObjectProvider<List<ViewResolver>> viewResolversProvider,
            ServerCodecConfigurer serverCodecConfigurer
    ) {
        this.viewResolvers = viewResolversProvider.getIfAvailable(Collections::emptyList);
        this.serverCodecConfigurer = serverCodecConfigurer;
    }

    /**
     * Sentinel 限流异常处理器：返回 429 JSON。
     * 注意：sentinelGatewayFilter 由 SentinelSCGAutoConfiguration 自动配置，无需手动定义。
     */
    @Bean
    @Order(Ordered.HIGHEST_PRECEDENCE)
    public SentinelGatewayBlockExceptionHandler sentinelGatewayBlockExceptionHandler() {
        return new SentinelGatewayBlockExceptionHandler(viewResolvers, serverCodecConfigurer);
    }

    /**
     * 初始化限流规则和 API 分组。
     */
    @PostConstruct
    public void initGatewayRules() {
        initApiDefinitions();
        initFlowRules();
        log.info("[Sentinel] Gateway 限流规则已初始化");
    }

    /**
     * API 分组定义：按业务模块分组，便于精细化限流。
     */
    private void initApiDefinitions() {
        Set<ApiDefinition> definitions = new HashSet<>();

        // Agent API 分组
        definitions.add(new ApiDefinition("agent_api")
                .setPredicateItems(Set.of(
                        new ApiPathPredicateItem()
                                .setPattern("/api/agent/**")
                                .setMatchStrategy(SentinelGatewayConstants.URL_MATCH_STRATEGY_PREFIX)
                )));

        // Auth API 分组
        definitions.add(new ApiDefinition("auth_api")
                .setPredicateItems(Set.of(
                        new ApiPathPredicateItem()
                                .setPattern("/api/auth/**")
                                .setMatchStrategy(SentinelGatewayConstants.URL_MATCH_STRATEGY_PREFIX)
                )));

        // Knowledge API 分组
        definitions.add(new ApiDefinition("knowledge_api")
                .setPredicateItems(Set.of(
                        new ApiPathPredicateItem()
                                .setPattern("/api/knowledge/**")
                                .setMatchStrategy(SentinelGatewayConstants.URL_MATCH_STRATEGY_PREFIX)
                )));

        // LLM API 分组
        definitions.add(new ApiDefinition("llm_api")
                .setPredicateItems(Set.of(
                        new ApiPathPredicateItem()
                                .setPattern("/api/llm/**")
                                .setMatchStrategy(SentinelGatewayConstants.URL_MATCH_STRATEGY_PREFIX)
                )));

        GatewayApiDefinitionManager.loadApiDefinitions(definitions);
    }

    /**
     * 限流规则定义。
     *
     * <p>规则说明：
     * <ul>
     *   <li>count: QPS 阈值</li>
     *   <li>intervalSec: 统计窗口（秒）</li>
     *   <li>burst: 突发容量</li>
     * </ul>
     */
    private void initFlowRules() {
        Set<GatewayFlowRule> rules = new HashSet<>();

        // 全局限流：200 QPS
        // （通过 route 级别，对每条路由限流）

        // Agent API: 50 QPS（LLM 调用成本高）
        rules.add(new GatewayFlowRule("agent_api")
                .setResourceMode(SentinelGatewayConstants.RESOURCE_MODE_CUSTOM_API_NAME)
                .setCount(50)
                .setIntervalSec(1)
                .setBurst(10));

        // Auth API: 20 QPS（防暴力破解）
        rules.add(new GatewayFlowRule("auth_api")
                .setResourceMode(SentinelGatewayConstants.RESOURCE_MODE_CUSTOM_API_NAME)
                .setCount(20)
                .setIntervalSec(1)
                .setBurst(5));

        // Knowledge API: 10 QPS（文件处理重）
        rules.add(new GatewayFlowRule("knowledge_api")
                .setResourceMode(SentinelGatewayConstants.RESOURCE_MODE_CUSTOM_API_NAME)
                .setCount(10)
                .setIntervalSec(1)
                .setBurst(3));

        // LLM API: 30 QPS
        rules.add(new GatewayFlowRule("llm_api")
                .setResourceMode(SentinelGatewayConstants.RESOURCE_MODE_CUSTOM_API_NAME)
                .setCount(30)
                .setIntervalSec(1)
                .setBurst(10));

        // 其他路由级别限流（按 route id）
        String[] generalRoutes = {
                "nexus-tenant", "nexus-session", "nexus-platform",
                "nexus-agent-config", "nexus-billing",
                "nexus-tool-registry", "nexus-memory", "nexus-rag"
        };
        for (String routeId : generalRoutes) {
            rules.add(new GatewayFlowRule(routeId)
                    .setResourceMode(SentinelGatewayConstants.RESOURCE_MODE_ROUTE_ID)
                    .setCount(100)
                    .setIntervalSec(1)
                    .setBurst(20));
        }

        GatewayRuleManager.loadRules(rules);
        log.info("[Sentinel] 已加载 {} 条限流规则", rules.size());
    }
}
