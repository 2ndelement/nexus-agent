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
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ConversationServiceImpl {

    private final ConversationMapper conversationMapper;
    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final ToolService toolService;

    private String metaKey(Long tenantId, String convId) {
        return "nexus:" + tenantId + ":conv:" + convId + ":meta";
    }

    /**
     * 创建会话，保存工具列表
     */
    @Transactional
    public Conversation create(Long tenantId, Long userId, CreateConversationRequest req) {
        // 1. 获取可用工具列表
        Map<String, Object> toolList = toolService.getAvailableTools(tenantId, userId);
        
        // 2. 创建会话
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
        
        // 3. 保存工具列表
        try {
            conv.setToolList(objectMapper.writeValueAsString(toolList));
        } catch (Exception e) {
            log.error("工具列表序列化失败", e);
            conv.setToolList("{}");
        }
        
        conversationMapper.insert(conv);
        log.info("创建会话 convId={} tenantId={} userId={} tools={}", 
            conv.getId(), tenantId, userId, ((List)toolList.get("tools")).size());
        
        return conv;
    }

    /**
     * 获取会话的工具列表
     */
    public Map<String, Object> getToolList(Long tenantId, String convId) {
        Conversation conv = conversationMapper.selectOne(
            new LambdaQueryWrapper<Conversation>()
                .eq(Conversation::getId, convId)
                .eq(Conversation::getTenantId, tenantId)
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
     * 列出当前用户（tenantId + userId）的所有会话，分页。
     */
    public PageResult<Conversation> listByUser(Long tenantId, Long userId, int page, int size) {
        long total = conversationMapper.selectCount(
            new LambdaQueryWrapper<Conversation>()
                .eq(Conversation::getTenantId, tenantId)
                .eq(Conversation::getUserId, userId)
                .eq(Conversation::getStatus, 1)
        );
        
        long offset = (long) (page - 1) * size;
        List<Conversation> records = conversationMapper.selectList(
            new LambdaQueryWrapper<Conversation>()
                .eq(Conversation::getTenantId, tenantId)
                .eq(Conversation::getUserId, userId)
                .eq(Conversation::getStatus, 1)
                .orderByDesc(Conversation::getUpdateTime)
                .last("LIMIT " + size + " OFFSET " + offset)
        );
        
        return PageResult.of(records, total, page, size);
    }

    /**
     * 获取会话详情，强制校验 tenantId 防止跨租户访问。
     */
    public Conversation getById(Long tenantId, String convId) {
        Conversation conv = conversationMapper.selectOne(
            new LambdaQueryWrapper<Conversation>()
                .eq(Conversation::getId, convId)
                .eq(Conversation::getTenantId, tenantId)
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
    public void archive(Long tenantId, Long userId, String convId) {
        Conversation conv = getById(tenantId, convId);
        if (!conv.getUserId().equals(userId)) {
            throw new BizException(ResultCode.FORBIDDEN, "无权操作此会话");
        }
        conversationMapper.update(null,
            new LambdaUpdateWrapper<Conversation>()
                .eq(Conversation::getId, convId)
                .eq(Conversation::getTenantId, tenantId)
                .set(Conversation::getStatus, 0)
                .set(Conversation::getUpdateTime, LocalDateTime.now())
        );
        redisTemplate.delete(metaKey(tenantId, convId));
        log.info("归档会话 convId={} tenantId={}", convId, tenantId);
    }

    /**
     * 更新会话标题。
     */
    @Transactional
    public void updateTitle(Long tenantId, Long userId, String convId, String title) {
        Conversation conv = getById(tenantId, convId);
        if (!conv.getUserId().equals(userId)) {
            throw new BizException(ResultCode.FORBIDDEN, "无权操作此会话");
        }
        conversationMapper.update(null,
            new LambdaUpdateWrapper<Conversation>()
                .eq(Conversation::getId, convId)
                .eq(Conversation::getTenantId, tenantId)
                .set(Conversation::getTitle, title)
                .set(Conversation::getUpdateTime, LocalDateTime.now())
        );
        redisTemplate.delete(metaKey(tenantId, convId));
    }

    /**
     * 验证会话存在且属于指定租户。
     */
    public Conversation validateExists(Long tenantId, String convId) {
        return getById(tenantId, convId);
    }
}
