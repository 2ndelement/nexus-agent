package tech.nexus.session.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.PageResult;
import tech.nexus.common.result.ResultCode;
import tech.nexus.session.dto.AppendMessageRequest;
import tech.nexus.session.entity.Message;
import tech.nexus.session.mapper.MessageMapper;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 消息服务实现。
 *
 * <p>V5 重构：使用 owner_type + owner_id 替代 tenant_id
 * 追加消息使用幂等 Key 防重复写入。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class MessageServiceImpl {

    private final MessageMapper messageMapper;
    private final ConversationServiceImpl conversationService;
    private final StringRedisTemplate redisTemplate;

    // ─── Redis Key 生成 ────────────────────────────────────────────────────────

    private String recentMsgsKey(String ownerType, Long ownerId, String convId) {
        return "nexus:" + ownerType + ":" + ownerId + ":conv:" + convId + ":msgs:recent";
    }

    // ─── 获取消息历史（分页，按 create_time 升序）────────────────────────────

    /**
     * 获取消息历史，强制校验会话归属，按 create_time 升序返回。
     */
    public PageResult<Message> listMessages(String ownerType, Long ownerId, String convId, int page, int size) {
        // 验证会话存在且属于该空间
        conversationService.validateExists(ownerType, ownerId, convId);

        long total = messageMapper.selectCount(
                new LambdaQueryWrapper<Message>()
                        .eq(Message::getOwnerType, ownerType)
                        .eq(Message::getOwnerId, ownerId)
                        .eq(Message::getConversationId, convId));

        long offset = (long) (page - 1) * size;
        List<Message> messages = messageMapper.selectList(
                new LambdaQueryWrapper<Message>()
                        .eq(Message::getOwnerType, ownerType)
                        .eq(Message::getOwnerId, ownerId)
                        .eq(Message::getConversationId, convId)
                        .orderByAsc(Message::getCreateTime)
                        .last("LIMIT " + size + " OFFSET " + offset));

        return PageResult.of(messages, total, page, size);
    }

    // ─── 追加消息（幂等）─────────────────────────────────────────────────────

    /**
     * 追加消息，支持幂等：若 idempotentKey 已存在则返回已有消息，不重复写入。
     */
    @Transactional
    public Message appendMessage(String ownerType, Long ownerId, String convId, AppendMessageRequest req) {
        // 验证会话存在且属于该空间
        conversationService.validateExists(ownerType, ownerId, convId);

        // 幂等检查
        if (req.getIdempotentKey() != null && !req.getIdempotentKey().isBlank()) {
            Message existing = messageMapper.selectOne(
                    new LambdaQueryWrapper<Message>()
                            .eq(Message::getOwnerType, ownerType)
                            .eq(Message::getOwnerId, ownerId)
                            .eq(Message::getConversationId, convId)
                            .eq(Message::getIdempotentKey, req.getIdempotentKey())
                            .last("LIMIT 1"));
            if (existing != null) {
                log.debug("幂等命中，跳过写入 idempotentKey={}", req.getIdempotentKey());
                return existing;
            }
        }

        Message msg = new Message();
        msg.setConversationId(convId);
        msg.setOwnerType(ownerType);
        msg.setOwnerId(ownerId);
        msg.setTenantId(ownerId);
        msg.setRole(req.getRole());
        msg.setContent(req.getContent());
        msg.setTokens(req.getTokens() != null ? req.getTokens() : 0);
        msg.setMetadata(req.getMetadata());
        msg.setIdempotentKey(req.getIdempotentKey());
        msg.setCreateTime(LocalDateTime.now());
        messageMapper.insert(msg);

        // 更新会话消息计数
        conversationService.incrementMessageCount(ownerType, ownerId, convId);

        // 清除最近消息缓存，下次查询时重建
        redisTemplate.delete(recentMsgsKey(ownerType, ownerId, convId));

        log.debug("追加消息 msgId={} convId={} ownerType={} ownerId={} role={}", msg.getId(), convId, ownerType, ownerId, req.getRole());
        return msg;
    }

    // ─── 清空消息 ─────────────────────────────────────────────────────────────

    /**
     * 清空会话下所有消息，强制校验空间归属。
     */
    @Transactional
    public void clearMessages(String ownerType, Long ownerId, String convId) {
        // 验证会话归属
        conversationService.validateExists(ownerType, ownerId, convId);

        messageMapper.delete(
                new LambdaQueryWrapper<Message>()
                        .eq(Message::getOwnerType, ownerType)
                        .eq(Message::getOwnerId, ownerId)
                        .eq(Message::getConversationId, convId));

        // 清除缓存
        redisTemplate.delete(recentMsgsKey(ownerType, ownerId, convId));
        log.debug("清空消息 convId={} ownerType={} ownerId={}", convId, ownerType, ownerId);
    }

    // ─── 按 convId 批量删除（归档会话时调用）─────────────────────────────────

    /**
     * 删除指定会话下所有消息（仅限同一空间内）。
     */
    @Transactional
    public void deleteByConvId(String ownerType, Long ownerId, String convId) {
        messageMapper.delete(
                new LambdaQueryWrapper<Message>()
                        .eq(Message::getOwnerType, ownerType)
                        .eq(Message::getOwnerId, ownerId)
                        .eq(Message::getConversationId, convId));
        redisTemplate.delete(recentMsgsKey(ownerType, ownerId, convId));
    }
}
