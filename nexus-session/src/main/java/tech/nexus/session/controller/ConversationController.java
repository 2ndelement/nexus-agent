package tech.nexus.session.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import tech.nexus.common.result.PageResult;
import tech.nexus.common.result.Result;
import tech.nexus.common.result.ResultCode;
import tech.nexus.session.dto.CreateConversationRequest;
import tech.nexus.session.dto.UpdateTitleRequest;
import tech.nexus.session.entity.Conversation;
import tech.nexus.session.service.impl.ConversationServiceImpl;

/**
 * 会话管理控制器。
 *
 * <p>所有接口通过 Gateway 注入的 X-Tenant-Id / X-User-Id Header 提取租户和用户上下文。
 * Gateway 负责 Token 验证，本服务只做业务逻辑。
 */
@RestController
@RequestMapping("/api/session/conversations")
@RequiredArgsConstructor
public class ConversationController {

    private final ConversationServiceImpl conversationService;

    // ─── POST /api/session/conversations ─────────────────────────────────────

    /**
     * 创建会话。
     *
     * V5 重构：支持 X-Owner-Type + X-Owner-Id（优先）或 X-Tenant-Id（兼容）
     */
    @PostMapping
    public Result<Conversation> create(
            @RequestHeader(value = "X-Owner-Type", required = false) String ownerType,
            @RequestHeader(value = "X-Owner-Id", required = false) Long ownerId,
            @RequestHeader(value = "X-Tenant-Id", required = false) Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @RequestBody(required = false) CreateConversationRequest req) {
        if (req == null) {
            req = new CreateConversationRequest();
        }
        // V5 优先使用 X-Owner-Type + X-Owner-Id，否则兼容 X-Tenant-Id
        String finalOwnerType = ownerType;
        Long finalOwnerId = ownerId;
        if (finalOwnerType == null || finalOwnerId == null) {
            finalOwnerType = "PERSONAL";
            finalOwnerId = tenantId;
        }
        Conversation conv = conversationService.create(finalOwnerType, finalOwnerId, userId, req);
        return Result.success(conv);
    }

    // ─── GET /api/session/conversations ──────────────────────────────────────

    /**
     * 列出当前用户所有会话（分页）。
     */
    @GetMapping
    public Result<PageResult<Conversation>> list(
            @RequestHeader(value = "X-Owner-Type", required = false) String ownerType,
            @RequestHeader(value = "X-Owner-Id", required = false) Long ownerId,
            @RequestHeader(value = "X-Tenant-Id", required = false) Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        String finalOwnerType = ownerType;
        Long finalOwnerId = ownerId;
        if (finalOwnerType == null || finalOwnerId == null) {
            finalOwnerType = "PERSONAL";
            finalOwnerId = tenantId;
        }
        PageResult<Conversation> result = conversationService.listByUser(finalOwnerType, finalOwnerId, userId, page, size);
        return Result.success(result);
    }

    // ─── GET /api/session/conversations/{id} ─────────────────────────────────

    /**
     * 获取会话详情。
     */
    @GetMapping("/{id}")
    public Result<Conversation> getById(
            @RequestHeader(value = "X-Owner-Type", required = false) String ownerType,
            @RequestHeader(value = "X-Owner-Id", required = false) Long ownerId,
            @RequestHeader(value = "X-Tenant-Id", required = false) Long tenantId,
            @PathVariable("id") String convId) {
        String finalOwnerType = ownerType;
        Long finalOwnerId = ownerId;
        if (finalOwnerType == null || finalOwnerId == null) {
            finalOwnerType = "PERSONAL";
            finalOwnerId = tenantId;
        }
        Conversation conv = conversationService.getById(finalOwnerType, finalOwnerId, convId);
        return Result.success(conv);
    }

    // ─── DELETE /api/session/conversations/{id} ───────────────────────────────

    /**
     * 归档（软删除）会话。
     */
    @DeleteMapping("/{id}")
    public Result<Void> archive(
            @RequestHeader(value = "X-Owner-Type", required = false) String ownerType,
            @RequestHeader(value = "X-Owner-Id", required = false) Long ownerId,
            @RequestHeader(value = "X-Tenant-Id", required = false) Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable("id") String convId) {
        String finalOwnerType = ownerType;
        Long finalOwnerId = ownerId;
        if (finalOwnerType == null || finalOwnerId == null) {
            finalOwnerType = "PERSONAL";
            finalOwnerId = tenantId;
        }
        conversationService.archive(finalOwnerType, finalOwnerId, userId, convId);
        return Result.success();
    }

    // ─── PUT /api/session/conversations/{id}/title ────────────────────────────

    /**
     * 更新会话标题。
     */
    @PutMapping("/{id}/title")
    public Result<Void> updateTitle(
            @RequestHeader(value = "X-Owner-Type", required = false) String ownerType,
            @RequestHeader(value = "X-Owner-Id", required = false) Long ownerId,
            @RequestHeader(value = "X-Tenant-Id", required = false) Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable("id") String convId,
            @Valid @RequestBody UpdateTitleRequest req) {
        String finalOwnerType = ownerType;
        Long finalOwnerId = ownerId;
        if (finalOwnerType == null || finalOwnerId == null) {
            finalOwnerType = "PERSONAL";
            finalOwnerId = tenantId;
        }
        conversationService.updateTitle(finalOwnerType, finalOwnerId, userId, convId, req.getTitle());
        return Result.success();
    }
}
