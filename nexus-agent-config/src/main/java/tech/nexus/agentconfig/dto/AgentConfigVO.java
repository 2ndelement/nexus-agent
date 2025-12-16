package tech.nexus.agentconfig.dto;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

/**
 * Agent 配置响应 VO。
 */
@Data
public class AgentConfigVO {

    private Long id;
    private Long tenantId;
    private String name;
    private String description;
    private String avatar;
    private String systemPrompt;
    private String model;
    private BigDecimal temperature;
    private Integer maxTokens;
    private List<String> tools;
    private List<Long> kbIds;
    private Integer version;
    private Integer status;
    private Integer isPublic;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
