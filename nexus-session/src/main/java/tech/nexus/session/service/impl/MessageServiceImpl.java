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
 * <p>所有查询必须携带 tenantId 条件；追加消息使用幂等 Key 防重复写入。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class MessageServiceImpl {

    private final MessageMapper messageMapper;
    private final ConversationServiceImpl conversationService;
    private final StringRedisTemplate redisTemplate;

    // ─── Redis Key 生成 ────────────────────────────────────────────────────────

    private String recentMsgsKey(Long tenantId, String convId) {
        return "nexus:" + tenantId + ":conv:" + convId + ":msgs:recent";
    }

    // ─── 获取消息历史（分页，按 create_time 升序）────────────────────────────

    /**
     * 获取消息历史，强制校验会话归属，按 create_time 升序返回。
     */
    public PageResult<Message> listMessages(Long tenantId, String convId, int page, int size) {
        // 验证会话存在且属于该租户
        conversationService.validateExists(tenantId, convId);

        long total = messageMapper.selectCount(
                new LambdaQueryWrapper<Message>()
                        .eq(Message::getTenantId, tenantId)
                        .eq(Message::getConversationId, convId));

        long offset = (long) (page - 1) * size;
        List<Message> messages = messageMapper.selectList(
                new LambdaQueryWrapper<Message>()
                        .eq(Message::getTenantId, tenantId)
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
    public Message appendMessage(Long tenantId, String convId, AppendMessageRequest req) {
        // 验证会话存在且属于该租户
        conversationService.validateExists(tenantId, convId);

        // 幂等检查
        if (req.getIdempotentKey() != null && !req.getIdempotentKey().isBlank()) {
            Message existing = messageMapper.selectOne(
                    new LambdaQueryWrapper<Message>()
                            .eq(Message::getTenantId, tenantId)
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
        msg.setTenantId(tenantId);
        msg.setRole(req.getRole());
        msg.setContent(req.getContent());
        msg.setTokens(req.getTokens() != null ? req.getTokens() : 0);
        msg.setMetadata(req.getMetadata());
        msg.setIdempotentKey(req.getIdempotentKey());
        msg.setCreateTime(LocalDateTime.now());
        messageMapper.insert(msg);

        // 更新会话消息计数
        conversationService.incrementMessageCount(tenantId, convId);

        // 清除最近消息缓存，下次查询时重建
        redisTemplate.delete(recentMsgsKey(tenantId, convId));

        log.debug("追加消息 msgId={} convId={} tenantId={} role={}", msg.getId(), convId, tenantId, req.getRole());
        return msg;
    }

    // ─── 清空消息 ─────────────────────────────────────────────────────────────

    /**
     * 清空会话下所有消息，强制校验 tenantId。
     */
    @Transactional
    public void clearMessages(Long tenantId, String convId) {
        // 验证会话归属
        conversationService.validateExists(tenantId, convId);

        messageMapper.delete(
                new LambdaQueryWrapper<Message>()
                        .eq(Message::getTenantId, tenantId)
                        .eq(Message::getConversationId, convId));

        // 清除缓存
        redisTemplate.delete(recentMsgsKey(tenantId, convId));
        log.debug("清空消息 convId={} tenantId={}", convId, tenantId);
    }

    // ─── 按 convId 批量删除（归档会话时调用）─────────────────────────────────

    /**
     * 删除指定会话下所有消息（仅限 tenantId 内）。
     */
    @Transactional
    public void deleteByConvId(Long tenantId, String convId) {
        messageMapper.delete(
                new LambdaQueryWrapper<Message>()
                        .eq(Message::getTenantId, tenantId)
                        .eq(Message::getConversationId, convId));
        redisTemplate.delete(recentMsgsKey(tenantId, convId));
    }
}
