package tech.nexus.session.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 更新会话标题请求 DTO。
 */
@Data
public class UpdateTitleRequest {

    /** 新标题，不能为空 */
    @NotBlank(message = "标题不能为空")
    private String title;
}
