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
     */
    @PostMapping
    public Result<Conversation> create(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @RequestBody(required = false) CreateConversationRequest req) {
        if (req == null) {
            req = new CreateConversationRequest();
        }
        Conversation conv = conversationService.create(tenantId, userId, req);
        return Result.success(conv);
    }

    // ─── GET /api/session/conversations ──────────────────────────────────────

    /**
     * 列出当前用户所有会话（分页）。
     */
    @GetMapping
    public Result<PageResult<Conversation>> list(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        PageResult<Conversation> result = conversationService.listByUser(tenantId, userId, page, size);
        return Result.success(result);
    }

    // ─── GET /api/session/conversations/{id} ─────────────────────────────────

    /**
     * 获取会话详情。
     */
    @GetMapping("/{id}")
    public Result<Conversation> getById(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @PathVariable("id") String convId) {
        Conversation conv = conversationService.getById(tenantId, convId);
        return Result.success(conv);
    }

    // ─── DELETE /api/session/conversations/{id} ───────────────────────────────

    /**
     * 归档（软删除）会话。
     */
    @DeleteMapping("/{id}")
    public Result<Void> archive(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable("id") String convId) {
        conversationService.archive(tenantId, userId, convId);
        return Result.success();
    }

    // ─── PUT /api/session/conversations/{id}/title ────────────────────────────

    /**
     * 更新会话标题。
     */
    @PutMapping("/{id}/title")
    public Result<Void> updateTitle(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable("id") String convId,
            @Valid @RequestBody UpdateTitleRequest req) {
        conversationService.updateTitle(tenantId, userId, convId, req.getTitle());
        return Result.success();
    }
}
