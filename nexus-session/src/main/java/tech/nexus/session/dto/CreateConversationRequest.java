package tech.nexus.session.dto;

import lombok.Data;

/**
 * 创建会话请求 DTO。
 */
@Data
public class CreateConversationRequest {

    /** 会话ID（可选，由客户端指定，用于客户端先生成ID的场景） */
    private String conversationId;

    /** 对话标题（可选，默认 "新对话"） */
    private String title;

    /** 使用的 Agent 配置ID（可选） */
    private Long agentId;

    /** 使用的模型（可选） */
    private String model;
}
