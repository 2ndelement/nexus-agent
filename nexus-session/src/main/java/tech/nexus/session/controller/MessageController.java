package tech.nexus.session.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import tech.nexus.common.result.PageResult;
import tech.nexus.common.result.Result;
import tech.nexus.session.dto.AppendMessageRequest;
import tech.nexus.session.entity.Message;
import tech.nexus.session.service.impl.MessageServiceImpl;

/**
 * 消息管理控制器。
 *
 * <p>消息接口挂在会话路径下，通过 Gateway 注入的 Header 获取租户上下文。
 */
@RestController
@RequestMapping("/api/session/conversations/{convId}/messages")
@RequiredArgsConstructor
public class MessageController {

    private final MessageServiceImpl messageService;

    // ─── GET /api/session/conversations/{convId}/messages ────────────────────

    /**
     * 获取消息历史（分页，按时间升序）。
     */
    @GetMapping
    public Result<PageResult<Message>> list(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @PathVariable String convId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "50") int size) {
        PageResult<Message> result = messageService.listMessages(tenantId, convId, page, size);
        return Result.success(result);
    }

    // ─── POST /api/session/conversations/{convId}/messages ───────────────────

    /**
     * 追加消息（由 agent-engine 调用），支持幂等。
     */
    @PostMapping
    public Result<Message> append(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @PathVariable String convId,
            @Valid @RequestBody AppendMessageRequest req) {
        Message msg = messageService.appendMessage(tenantId, convId, req);
        return Result.success(msg);
    }

    // ─── DELETE /api/session/conversations/{convId}/messages ─────────────────

    /**
     * 清空会话下所有消息。
     */
    @DeleteMapping
    public Result<Void> clear(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @PathVariable String convId) {
        messageService.clearMessages(tenantId, convId);
        return Result.success();
    }
}
