package tech.nexus.session.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.PageResult;
import tech.nexus.common.result.ResultCode;
import tech.nexus.session.dto.CreateConversationRequest;
import tech.nexus.session.entity.Conversation;
import tech.nexus.session.mapper.ConversationMapper;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 会话服务实现。
 *
 * <p>所有查询必须携带 tenantId 条件，确保多租户数据隔离。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ConversationServiceImpl {

    private final ConversationMapper conversationMapper;
    private final StringRedisTemplate redisTemplate;

    // ─── Redis Key 生成 ────────────────────────────────────────────────────────

    private String metaKey(Long tenantId, String convId) {
        return "nexus:" + tenantId + ":conv:" + convId + ":meta";
    }

    // ─── 创建会话 ─────────────────────────────────────────────────────────────

    /**
     * 创建会话，convId 使用 UUID，不使用自增 ID。
     */
    @Transactional
    public Conversation create(Long tenantId, Long userId, CreateConversationRequest req) {
        Conversation conv = new Conversation();
        conv.setId(UUID.randomUUID().toString().replace("-", ""));
        conv.setTenantId(tenantId);
        conv.setUserId(userId);
        conv.setTitle(req.getTitle() != null ? req.getTitle() : "新对话");
        conv.setAgentId(req.getAgentId());
        conv.setModel(req.getModel() != null ? req.getModel() : "MiniMax-M2.5-highspeed");
        conv.setStatus(1);
        conv.setMessageCount(0);
        conv.setCreateTime(LocalDateTime.now());
        conv.setUpdateTime(LocalDateTime.now());
        conversationMapper.insert(conv);
        log.debug("创建会话 convId={} tenantId={} userId={}", conv.getId(), tenantId, userId);
        return conv;
    }

    // ─── 分页列表 ─────────────────────────────────────────────────────────────

    /**
     * 列出当前用户（tenantId + userId）的所有会话，分页。
     */
    public PageResult<Conversation> listByUser(Long tenantId, Long userId, int page, int size) {
        LambdaQueryWrapper<Conversation> countWrapper = new LambdaQueryWrapper<Conversation>()
                .eq(Conversation::getTenantId, tenantId)
                .eq(Conversation::getUserId, userId)
                .eq(Conversation::getStatus, 1);

        long total = conversationMapper.selectCount(countWrapper);

        long offset = (long) (page - 1) * size;
        List<Conversation> records = conversationMapper.selectList(
                new LambdaQueryWrapper<Conversation>()
                        .eq(Conversation::getTenantId, tenantId)
                        .eq(Conversation::getUserId, userId)
                        .eq(Conversation::getStatus, 1)
                        .orderByDesc(Conversation::getUpdateTime)
                        .last("LIMIT " + size + " OFFSET " + offset));

        return PageResult.of(records, total, page, size);
    }

    // ─── 获取详情 ─────────────────────────────────────────────────────────────

    /**
     * 获取会话详情，强制校验 tenantId 防止跨租户访问。
     */
    public Conversation getById(Long tenantId, String convId) {
        Conversation conv = conversationMapper.selectOne(
                new LambdaQueryWrapper<Conversation>()
                        .eq(Conversation::getId, convId)
                        .eq(Conversation::getTenantId, tenantId));
        if (conv == null) {
            throw new BizException(ResultCode.NOT_FOUND, "会话不存在");
        }
        return conv;
    }

    // ─── 归档（软删除）─────────────────────────────────────────────────────────

    /**
     * 归档会话（设 status=0），同时使缓存失效。
     */
    @Transactional
    public void archive(Long tenantId, Long userId, String convId) {
        // 先验证归属
        Conversation conv = getById(tenantId, convId);
        if (!conv.getUserId().equals(userId)) {
            throw new BizException(ResultCode.FORBIDDEN, "无权操作该会话");
        }
        conversationMapper.update(null,
                new LambdaUpdateWrapper<Conversation>()
                        .eq(Conversation::getId, convId)
                        .eq(Conversation::getTenantId, tenantId)
                        .set(Conversation::getStatus, 0)
                        .set(Conversation::getUpdateTime, LocalDateTime.now()));
        // 清除缓存
        redisTemplate.delete(metaKey(tenantId, convId));
        log.debug("归档会话 convId={} tenantId={}", convId, tenantId);
    }

    // ─── 更新标题 ─────────────────────────────────────────────────────────────

    /**
     * 更新会话标题。
     */
    @Transactional
    public void updateTitle(Long tenantId, Long userId, String convId, String title) {
        Conversation conv = getById(tenantId, convId);
        if (!conv.getUserId().equals(userId)) {
            throw new BizException(ResultCode.FORBIDDEN, "无权操作该会话");
        }
        conversationMapper.update(null,
                new LambdaUpdateWrapper<Conversation>()
                        .eq(Conversation::getId, convId)
                        .eq(Conversation::getTenantId, tenantId)
                        .set(Conversation::getTitle, title)
                        .set(Conversation::getUpdateTime, LocalDateTime.now()));
        // 更新缓存（直接清除，下次查询时重建）
        redisTemplate.delete(metaKey(tenantId, convId));
    }

    // ─── 增加消息计数 ─────────────────────────────────────────────────────────

    /**
     * 增加会话消息计数（由 MessageServiceImpl 调用）。
     */
    @Transactional
    public void incrementMessageCount(Long tenantId, String convId) {
        conversationMapper.update(null,
                new LambdaUpdateWrapper<Conversation>()
                        .eq(Conversation::getId, convId)
                        .eq(Conversation::getTenantId, tenantId)
                        .setSql("message_count = message_count + 1")
                        .set(Conversation::getUpdateTime, LocalDateTime.now()));
    }

    // ─── 验证会话存在且属于该租户 ─────────────────────────────────────────────

    /**
     * 校验会话存在且属于指定 tenantId（不校验 userId，供 agent-engine 调用）。
     */
    public Conversation validateExists(Long tenantId, String convId) {
        return getById(tenantId, convId);
    }
}
