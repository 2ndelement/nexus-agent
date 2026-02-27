package tech.nexus.session.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;
import tech.nexus.common.result.PageResult;
import tech.nexus.common.result.Result;
import tech.nexus.session.dto.CreateBotBindingRequest;
import tech.nexus.session.entity.Bot;
import tech.nexus.session.entity.BotBinding;
import tech.nexus.session.service.BotBindingService;
import tech.nexus.session.service.BotService;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Bot 管理控制器。
 *
 * <p>提供 Bot 和 BotBinding 的管理接口。
 */
@RestController
@RequestMapping("/api/session")
@RequiredArgsConstructor
public class BotController {

    private final BotService botService;
    private final BotBindingService botBindingService;

    // ==================== Bot 接口 ====================

    /**
     * 列出 Bot（分页、过滤）。
     * 支持按 owner_type/owner_id 或 platform 过滤。
     */
    @GetMapping("/bots")
    public Result<PageResult<Bot>> listBots(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String ownerType,
            @RequestParam(required = false) Long ownerId,
            @RequestParam(required = false) String platform,
            @RequestParam(required = false) Integer status) {

        PageResult<Bot> result = botService.pageBots(ownerType, ownerId, platform, status, page, size);
        return Result.success(result);
    }

    /**
     * 获取 Bot 详情。
     */
    @GetMapping("/bots/{id}")
    public Result<Bot> getBot(@PathVariable("id") Long id) {
        return botService.findById(id)
                .map(Result::success)
                .orElse(Result.fail(404, "Bot 不存在"));
    }

    // ==================== BotBinding 接口 ====================

    /**
     * 列出当前用户的 Bot 绑定。
     */
    @GetMapping("/bot-bindings")
    public Result<List<Map<String, Object>>> listBotBindings(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @RequestParam(required = false) Long botId) {

        List<BotBinding> bindings;
        if (botId != null) {
            bindings = botBindingService.findByUserIdAndBotId(userId, botId)
                    .map(List::of)
                    .orElse(List.of());
        } else {
            bindings = botBindingService.findByUserId(userId);
        }

        // 填充 Bot 信息
        List<Map<String, Object>> result = bindings.stream().map(binding -> {
            Map<String, Object> item = new HashMap<>();
            item.put("id", binding.getId());
            item.put("botId", binding.getBotId());
            item.put("puid", binding.getPuid());
            item.put("extraData", binding.getExtraData());
            item.put("status", binding.getStatus());
            item.put("createTime", binding.getCreateTime());

            // 查询 Bot 信息
            botService.findById(binding.getBotId()).ifPresent(bot -> {
                item.put("botName", bot.getBotName());
                item.put("botPlatform", bot.getPlatform());
                item.put("botStatus", bot.getStatus());
            });

            return item;
        }).collect(Collectors.toList());

        return Result.success(result);
    }

    /**
     * 创建 Bot 绑定。
     * 将当前用户与指定 Bot 的平台账号（puid）绑定。
     */
    @PostMapping("/bot-bindings")
    public Result<BotBinding> createBotBinding(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @RequestBody CreateBotBindingRequest req) {

        if (req.getBotId() == null || !StringUtils.hasText(req.getPuid())) {
            return Result.fail(400, "botId 和 puid 不能为空");
        }

        // 验证 Bot 是否存在
        if (botService.findById(req.getBotId()).isEmpty()) {
            return Result.fail(404, "Bot 不存在");
        }

        @SuppressWarnings("unchecked")
        Map<String, Object> extraData = req.getExtraData() instanceof Map
                ? (Map<String, Object>) req.getExtraData()
                : null;

        BotBinding binding = botBindingService.createOrUpdateBinding(
                req.getBotId(),
                userId,
                req.getPuid(),
                extraData
        );

        return Result.success(binding);
    }

    /**
     * 解绑（删除 BotBinding）。
     */
    @DeleteMapping("/bot-bindings/{id}")
    public Result<Void> deleteBotBinding(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable("id") Long bindingId) {

        botBindingService.unbind(bindingId);
        return Result.success();
    }
}
