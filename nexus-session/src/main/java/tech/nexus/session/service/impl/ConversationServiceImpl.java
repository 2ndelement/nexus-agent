package tech.nexus.session.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.fasterxml.jackson.databind.ObjectMapper;
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
import tech.nexus.session.service.ToolService;

import java.time.LocalDateTime;
import java.util.*;

/**
 * 会话服务实现。
 *
 * V5 重构：使用 owner_type + owner_id 替代 tenant_id
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ConversationServiceImpl {

    private final ConversationMapper conversationMapper;
    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final ToolService toolService;

    private String metaKey(String ownerType, Long ownerId, String convId) {
        return "nexus:" + ownerType + ":" + ownerId + ":conv:" + convId + ":meta";
    }

    /**
     * 创建会话，保存工具列表
     */
    @Transactional
    public Conversation create(String ownerType, Long ownerId, Long userId, CreateConversationRequest req) {
        // 1. 获取可用工具列表（V5: 根据 ownerType 和 ownerId 获取）
        Map<String, Object> toolList;
        try {
            toolList = toolService.getAvailableTools(ownerType, ownerId, userId);
        } catch (Exception e) {
            log.error("获取工具列表失败，降级为空列表 ownerType={} ownerId={} userId={}", ownerType, ownerId, userId, e);
            toolList = Map.of("updated_at", new Date(), "tools", Collections.emptyList());
        }

        // 2. 创建会话
        Conversation conv = new Conversation();
        // 支持客户端指定会话ID，否则服务端生成
        if (req.getConversationId() != null && !req.getConversationId().isEmpty()) {
            conv.setConversationId(req.getConversationId());
        } else {
            conv.setConversationId(UUID.randomUUID().toString().replace("-", ""));
        }
        conv.setOwnerType(ownerType);
        conv.setOwnerId(ownerId);
        conv.setTenantId(ownerId);
        conv.setUserId(userId);
        conv.setTitle(req.getTitle() != null ? req.getTitle() : "新对话");
        conv.setAgentId(req.getAgentId());
        conv.setModel(req.getModel() != null ? req.getModel() : "MiniMax-M2.5-highspeed");
        conv.setStatus(1);
        conv.setMessageCount(0);
        conv.setCreateTime(LocalDateTime.now());
        conv.setUpdateTime(LocalDateTime.now());

        // 3. 保存工具列表
        try {
            conv.setToolList(objectMapper.writeValueAsString(toolList));
        } catch (Exception e) {
            log.error("工具列表序列化失败", e);
            conv.setToolList("{}");
        }

        conversationMapper.insert(conv);
        log.info("创建会话 convId={} ownerType={} ownerId={} userId={} tools={}",
            conv.getConversationId(), ownerType, ownerId, userId, ((List)toolList.get("tools")).size());

        return conv;
    }

    /**
     * 获取会话的工具列表
     */
    public Map<String, Object> getToolList(String ownerType, Long ownerId, String convId) {
        Conversation conv = conversationMapper.selectOne(
            new LambdaQueryWrapper<Conversation>()
                .eq(Conversation::getConversationId, convId)
                .eq(Conversation::getOwnerType, ownerType)
                .eq(Conversation::getOwnerId, ownerId)
        );

        if (conv == null) {
            throw new BizException(ResultCode.NOT_FOUND, "会话不存在");
        }

        try {
            if (conv.getToolList() != null) {
                return objectMapper.readValue(conv.getToolList(), Map.class);
            }
        } catch (Exception e) {
            log.error("工具列表解析失败 convId={}", convId, e);
        }

        return Map.of("tools", Collections.emptyList());
    }

    /**
     * 列出当前用户的所有会话，分页。
     * V5: 根据 ownerType + ownerId + userId 查询
     */
    public PageResult<Conversation> listByUser(String ownerType, Long ownerId, Long userId, int page, int size) {
        long total = conversationMapper.selectCount(
            new LambdaQueryWrapper<Conversation>()
                .eq(Conversation::getOwnerType, ownerType)
                .eq(Conversation::getOwnerId, ownerId)
                .eq(Conversation::getUserId, userId)
                .eq(Conversation::getStatus, 1)
        );

        long offset = (long) (page - 1) * size;
        List<Conversation> records = conversationMapper.selectList(
            new LambdaQueryWrapper<Conversation>()
                .eq(Conversation::getOwnerType, ownerType)
                .eq(Conversation::getOwnerId, ownerId)
                .eq(Conversation::getUserId, userId)
                .eq(Conversation::getStatus, 1)
                .orderByDesc(Conversation::getUpdateTime)
                .last("LIMIT " + size + " OFFSET " + offset)
        );

        return PageResult.of(records, total, page, size);
    }

    /**
     * 获取会话详情，强制校验 ownerType + ownerId 防止跨空间访问。
     */
    public Conversation getById(String ownerType, Long ownerId, String convId) {
        Conversation conv = conversationMapper.selectOne(
            new LambdaQueryWrapper<Conversation>()
                .eq(Conversation::getConversationId, convId)
                .eq(Conversation::getOwnerType, ownerType)
                .eq(Conversation::getOwnerId, ownerId)
        );
        if (conv == null) {
            throw new BizException(ResultCode.NOT_FOUND, "会话不存在");
        }
        return conv;
    }

    /**
     * 归档会话（软删除），同时使缓存失效。
     */
    @Transactional
    public void archive(String ownerType, Long ownerId, Long userId, String convId) {
        Conversation conv = getById(ownerType, ownerId, convId);
        if (!conv.getUserId().equals(userId)) {
            throw new BizException(ResultCode.FORBIDDEN, "无权操作此会话");
        }
        conversationMapper.update(null,
            new LambdaUpdateWrapper<Conversation>()
                .eq(Conversation::getConversationId, convId)
                .eq(Conversation::getOwnerType, ownerType)
                .eq(Conversation::getOwnerId, ownerId)
                .set(Conversation::getStatus, 0)
                .set(Conversation::getUpdateTime, LocalDateTime.now())
        );
        redisTemplate.delete(metaKey(ownerType, ownerId, convId));
        log.info("归档会话 convId={} ownerType={} ownerId={}", convId, ownerType, ownerId);
    }

    /**
     * 更新会话标题。
     */
    @Transactional
    public void updateTitle(String ownerType, Long ownerId, Long userId, String convId, String title) {
        Conversation conv = getById(ownerType, ownerId, convId);
        if (!conv.getUserId().equals(userId)) {
            throw new BizException(ResultCode.FORBIDDEN, "无权操作此会话");
        }
        conversationMapper.update(null,
            new LambdaUpdateWrapper<Conversation>()
                .eq(Conversation::getConversationId, convId)
                .eq(Conversation::getOwnerType, ownerType)
                .eq(Conversation::getOwnerId, ownerId)
                .set(Conversation::getTitle, title)
                .set(Conversation::getUpdateTime, LocalDateTime.now())
        );
        redisTemplate.delete(metaKey(ownerType, ownerId, convId));
    }

    /**
     * 验证会话存在且属于指定空间。
     */
    public Conversation validateExists(String ownerType, Long ownerId, String convId) {
        return getById(ownerType, ownerId, convId);
    }

    /**
     * 增加会话消息计数。
     */
    @Transactional
    public void incrementMessageCount(String ownerType, Long ownerId, String convId) {
        conversationMapper.update(null,
            new LambdaUpdateWrapper<Conversation>()
                .eq(Conversation::getConversationId, convId)
                .eq(Conversation::getOwnerType, ownerType)
                .eq(Conversation::getOwnerId, ownerId)
                .setSql("message_count = message_count + 1")
                .set(Conversation::getUpdateTime, LocalDateTime.now())
        );
        redisTemplate.delete(metaKey(ownerType, ownerId, convId));
    }
}
