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
     *
     * V5 重构：支持 X-Owner-Type + X-Owner-Id（优先）或 X-Tenant-Id（兼容）
     */
    @GetMapping
    public Result<PageResult<Message>> list(
            @RequestHeader(value = "X-Owner-Type", required = false) String ownerType,
            @RequestHeader(value = "X-Owner-Id", required = false) Long ownerId,
            @RequestHeader(value = "X-Tenant-Id", required = false) Long tenantId,
            @PathVariable String convId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "50") int size) {
        // V5 优先使用 X-Owner-Type + X-Owner-Id，否则兼容 X-Tenant-Id
        String finalOwnerType = ownerType;
        Long finalOwnerId = ownerId;
        if (finalOwnerType == null || finalOwnerId == null) {
            // 兼容旧版：X-Tenant-Id 作为个人空间处理
            finalOwnerType = "PERSONAL";
            finalOwnerId = tenantId;
        }
        PageResult<Message> result = messageService.listMessages(finalOwnerType, finalOwnerId, convId, page, size);
        return Result.success(result);
    }

    // ─── POST /api/session/conversations/{convId}/messages ───────────────────

    /**
     * 追加消息（由 agent-engine 调用），支持幂等。
     *
     * V5 重构：支持 X-Owner-Type + X-Owner-Id（优先）或 X-Tenant-Id（兼容）
     */
    @PostMapping
    public Result<Message> append(
            @RequestHeader(value = "X-Owner-Type", required = false) String ownerType,
            @RequestHeader(value = "X-Owner-Id", required = false) Long ownerId,
            @RequestHeader(value = "X-Tenant-Id", required = false) Long tenantId,
            @PathVariable String convId,
            @Valid @RequestBody AppendMessageRequest req) {
        // V5 优先使用 X-Owner-Type + X-Owner-Id，否则兼容 X-Tenant-Id
        String finalOwnerType = ownerType;
        Long finalOwnerId = ownerId;
        if (finalOwnerType == null || finalOwnerId == null) {
            finalOwnerType = "PERSONAL";
            finalOwnerId = tenantId;
        }
        Message msg = messageService.appendMessage(finalOwnerType, finalOwnerId, convId, req);
        return Result.success(msg);
    }

    // ─── DELETE /api/session/conversations/{convId}/messages ─────────────────

    /**
     * 清空会话下所有消息。
     *
     * V5 重构：支持 X-Owner-Type + X-Owner-Id（优先）或 X-Tenant-Id（兼容）
     */
    @DeleteMapping
    public Result<Void> clear(
            @RequestHeader(value = "X-Owner-Type", required = false) String ownerType,
            @RequestHeader(value = "X-Owner-Id", required = false) Long ownerId,
            @RequestHeader(value = "X-Tenant-Id", required = false) Long tenantId,
            @PathVariable String convId) {
        String finalOwnerType = ownerType;
        Long finalOwnerId = ownerId;
        if (finalOwnerType == null || finalOwnerId == null) {
            finalOwnerType = "PERSONAL";
            finalOwnerId = tenantId;
        }
        messageService.clearMessages(finalOwnerType, finalOwnerId, convId);
        return Result.success();
    }
}
