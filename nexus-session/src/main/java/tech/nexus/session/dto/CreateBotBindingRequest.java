package tech.nexus.session.dto;

import lombok.Data;

/**
 * 创建 Bot 绑定请求 DTO。
 */
@Data
public class CreateBotBindingRequest {

    /** Bot ID */
    private Long botId;

    /** 平台用户 ID（puid） */
    private String puid;

    /** 平台特定数据（可选） */
    private Object extraData;
}
