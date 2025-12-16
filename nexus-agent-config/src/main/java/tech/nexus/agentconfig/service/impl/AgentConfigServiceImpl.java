package tech.nexus.agentconfig.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import tech.nexus.agentconfig.dto.AgentConfigRequest;
import tech.nexus.agentconfig.dto.AgentConfigVO;
import tech.nexus.agentconfig.entity.AgentConfig;
import tech.nexus.agentconfig.entity.AgentConfigHistory;
import tech.nexus.agentconfig.mapper.AgentConfigHistoryMapper;
import tech.nexus.agentconfig.mapper.AgentConfigMapper;
import tech.nexus.agentconfig.service.AgentConfigService;
import tech.nexus.agentconfig.service.ToolRegistryService;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.ResultCode;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Agent 配置服务实现。
 *
 * <p>核心规则：
 * <ol>
 *   <li>更新时先写 history 表，再更新主表（Code Review 要求，顺序不可反）</li>
 *   <li>Redis 缓存 key 含 tenantId：nexus:{tenantId}:agent:{agentId}:config</li>
 *   <li>temperature 范围 0.0 ~ 2.0（Bean Validation 已覆盖，此处仍防御性校验）</li>
 *   <li>工具名必须在 tool_registry 中已注册</li>
 * </ol>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AgentConfigServiceImpl implements AgentConfigService {

    private final AgentConfigMapper agentConfigMapper;
    private final AgentConfigHistoryMapper historyMapper;
    private final ToolRegistryService toolRegistryService;
    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;

    private static final Duration CACHE_TTL = Duration.ofMinutes(5);
    private static final String CACHE_KEY_PATTERN = "nexus:%d:agent:%d:config";

    // ────────────────────────────────────────────────────────
    // CRUD
    // ────────────────────────────────────────────────────────

    @Override
    @Transactional(rollbackFor = Exception.class)
    public AgentConfigVO create(Long tenantId, AgentConfigRequest req) {
        validateRequest(req);

        // 名称唯一性校验
        long count = agentConfigMapper.selectCount(
                new LambdaQueryWrapper<AgentConfig>()
                        .eq(AgentConfig::getTenantId, tenantId)
                        .eq(AgentConfig::getName, req.getName())
        );
        if (count > 0) {
            throw new BizException(ResultCode.PARAM_ERROR, "Agent 名称已存在：" + req.getName());
        }

        AgentConfig entity = toEntity(tenantId, req);
        entity.setVersion(1);
        entity.setCreateTime(LocalDateTime.now());
        entity.setUpdateTime(LocalDateTime.now());
        agentConfigMapper.insert(entity);

        log.info("Created agent[{}] tenant={} name={}", entity.getId(), tenantId, entity.getName());
        return toVO(entity);
    }

    @Override
    public Page<AgentConfigVO> list(Long tenantId, String name, int page, int size) {
        LambdaQueryWrapper<AgentConfig> wrapper = new LambdaQueryWrapper<AgentConfig>()
                .eq(AgentConfig::getTenantId, tenantId)
                .like(StringUtils.hasText(name), AgentConfig::getName, name)
                .orderByDesc(AgentConfig::getUpdateTime);

        Page<AgentConfig> entityPage = agentConfigMapper.selectPage(new Page<>(page, size), wrapper);

        Page<AgentConfigVO> voPage = new Page<>(entityPage.getCurrent(), entityPage.getSize(), entityPage.getTotal());
        voPage.setRecords(entityPage.getRecords().stream().map(this::toVO).collect(Collectors.toList()));
        return voPage;
    }

    @Override
    public AgentConfigVO getById(Long tenantId, Long id) {
        // 先查 Redis 缓存
        String cacheKey = String.format(CACHE_KEY_PATTERN, tenantId, id);
        String cached = redisTemplate.opsForValue().get(cacheKey);
        if (cached != null) {
            try {
                return objectMapper.readValue(cached, AgentConfigVO.class);
            } catch (Exception e) {
                log.warn("Cache deserialization failed for key={}, fallback to DB", cacheKey);
            }
        }

        AgentConfig entity = fetchAndValidate(tenantId, id);
        AgentConfigVO vo = toVO(entity);

        // 写入缓存
        try {
            redisTemplate.opsForValue().set(cacheKey, objectMapper.writeValueAsString(vo), CACHE_TTL);
        } catch (Exception e) {
            log.warn("Cache set failed for key={}", cacheKey);
        }
        return vo;
    }

    /**
     * 更新 Agent。
     * <b>必须先写 history 表，再更新主表。</b>
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public AgentConfigVO update(Long tenantId, Long id, AgentConfigRequest req) {
        validateRequest(req);

        AgentConfig existing = fetchAndValidate(tenantId, id);

        // ① 先写历史快照（顺序不可反）
        saveHistory(existing, req.getChangeNote());

        // ② 更新主表
        AgentConfig updated = toEntity(tenantId, req);
        updated.setId(id);
        updated.setTenantId(tenantId);
        updated.setVersion(existing.getVersion() + 1);
        updated.setCreateTime(existing.getCreateTime());
        updated.setUpdateTime(LocalDateTime.now());
        agentConfigMapper.updateById(updated);

        // ③ 失效缓存
        evictCache(tenantId, id);

        log.info("Updated agent[{}] tenant={} v{}->{}", id, tenantId, existing.getVersion(), updated.getVersion());
        return toVO(updated);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(Long tenantId, Long id) {
        fetchAndValidate(tenantId, id);
        agentConfigMapper.deleteById(id);
        evictCache(tenantId, id);
        log.info("Deleted agent[{}] tenant={}", id, tenantId);
    }

    // ────────────────────────────────────────────────────────
    // 版本管理
    // ────────────────────────────────────────────────────────

    @Override
    public List<AgentConfigHistory> listHistory(Long tenantId, Long agentId) {
        fetchAndValidate(tenantId, agentId);
        return historyMapper.selectList(
                new LambdaQueryWrapper<AgentConfigHistory>()
                        .eq(AgentConfigHistory::getAgentId, agentId)
                        .eq(AgentConfigHistory::getTenantId, tenantId)
                        .orderByDesc(AgentConfigHistory::getVersion)
        );
    }

    /**
     * 回滚到指定版本。
     * <p>版本号继续 +1，不覆盖历史（即当前版本变成 currentVersion+1，内容恢复为 targetVersion）。
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public AgentConfigVO rollback(Long tenantId, Long agentId, int targetVersion) {
        AgentConfig current = fetchAndValidate(tenantId, agentId);

        AgentConfigHistory targetHistory = historyMapper.selectOne(
                new LambdaQueryWrapper<AgentConfigHistory>()
                        .eq(AgentConfigHistory::getAgentId, agentId)
                        .eq(AgentConfigHistory::getTenantId, tenantId)
                        .eq(AgentConfigHistory::getVersion, targetVersion)
        );
        if (targetHistory == null) {
            throw new BizException(ResultCode.NOT_FOUND,
                    "版本 v" + targetVersion + " 不存在");
        }

        // ① 先保存当前版本到历史
        saveHistory(current, "rollback from v" + current.getVersion() + " to v" + targetVersion);

        // ② 从快照恢复
        AgentConfig restored;
        try {
            restored = objectMapper.readValue(targetHistory.getSnapshot(), AgentConfig.class);
        } catch (JsonProcessingException e) {
            throw new BizException(ResultCode.INTERNAL_ERROR, "历史快照解析失败");
        }
        restored.setId(agentId);
        restored.setTenantId(tenantId);
        restored.setVersion(current.getVersion() + 1);
        restored.setUpdateTime(LocalDateTime.now());
        agentConfigMapper.updateById(restored);

        evictCache(tenantId, agentId);
        log.info("Rolled back agent[{}] tenant={} to v{}, new version={}", agentId, tenantId, targetVersion, restored.getVersion());
        return toVO(restored);
    }

    // ────────────────────────────────────────────────────────
    // 模板
    // ────────────────────────────────────────────────────────

    @Override
    public List<AgentConfigVO> listTemplates() {
        List<AgentConfig> templates = agentConfigMapper.selectList(
                new LambdaQueryWrapper<AgentConfig>()
                        .eq(AgentConfig::getIsPublic, 1)
                        .eq(AgentConfig::getStatus, 1)
        );
        return templates.stream().map(this::toVO).collect(Collectors.toList());
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public AgentConfigVO forkTemplate(Long tenantId, Long templateId) {
        AgentConfig template = agentConfigMapper.selectOne(
                new LambdaQueryWrapper<AgentConfig>()
                        .eq(AgentConfig::getId, templateId)
                        .eq(AgentConfig::getIsPublic, 1)
        );
        if (template == null) {
            throw new BizException(ResultCode.NOT_FOUND, "模板不存在或无权访问");
        }

        AgentConfig forked = new AgentConfig();
        forked.setTenantId(tenantId);
        forked.setName(template.getName() + "_copy");
        forked.setDescription(template.getDescription());
        forked.setAvatar(template.getAvatar());
        forked.setSystemPrompt(template.getSystemPrompt());
        forked.setModel(template.getModel());
        forked.setTemperature(template.getTemperature());
        forked.setMaxTokens(template.getMaxTokens());
        forked.setTools(template.getTools());
        forked.setKbIds(template.getKbIds());
        forked.setVersion(1);
        forked.setStatus(0); // 草稿
        forked.setIsPublic(0);
        forked.setCreateTime(LocalDateTime.now());
        forked.setUpdateTime(LocalDateTime.now());
        agentConfigMapper.insert(forked);

        log.info("Forked template[{}] for tenant={}, new agent[{}]", templateId, tenantId, forked.getId());
        return toVO(forked);
    }

    // ────────────────────────────────────────────────────────
    // Private Helpers
    // ────────────────────────────────────────────────────────

    private AgentConfig fetchAndValidate(Long tenantId, Long id) {
        AgentConfig entity = agentConfigMapper.selectById(id);
        if (entity == null) {
            throw new BizException(ResultCode.NOT_FOUND, "Agent 不存在：id=" + id);
        }
        // 租户隔离：禁止跨租户访问
        if (!entity.getTenantId().equals(tenantId)) {
            throw new BizException(ResultCode.FORBIDDEN, "无权访问该 Agent");
        }
        return entity;
    }

    private void validateRequest(AgentConfigRequest req) {
        // 防御性校验 temperature（Bean Validation 主要防线，这里兜底）
        if (req.getTemperature() != null) {
            double t = req.getTemperature().doubleValue();
            if (t < 0.0 || t > 2.0) {
                throw new BizException(ResultCode.PARAM_ERROR, "temperature 必须在 0.0 ~ 2.0 之间");
            }
        }
        // 工具合法性校验
        if (req.getTools() != null && !req.getTools().isEmpty()) {
            toolRegistryService.validateToolNames(req.getTools());
        }
    }

    private void saveHistory(AgentConfig entity, String changeNote) {
        AgentConfigHistory history = new AgentConfigHistory();
        history.setAgentId(entity.getId());
        history.setTenantId(entity.getTenantId());
        history.setVersion(entity.getVersion());
        history.setChangeNote(changeNote);
        history.setCreateTime(LocalDateTime.now());
        try {
            history.setSnapshot(objectMapper.writeValueAsString(entity));
        } catch (JsonProcessingException e) {
            throw new BizException(ResultCode.INTERNAL_ERROR, "快照序列化失败");
        }
        historyMapper.insert(history);
    }

    private void evictCache(Long tenantId, Long id) {
        String cacheKey = String.format(CACHE_KEY_PATTERN, tenantId, id);
        redisTemplate.delete(cacheKey);
    }

    @SuppressWarnings("unchecked")
    private AgentConfig toEntity(Long tenantId, AgentConfigRequest req) {
        AgentConfig entity = new AgentConfig();
        entity.setTenantId(tenantId);
        entity.setName(req.getName());
        entity.setDescription(req.getDescription());
        entity.setAvatar(req.getAvatar());
        entity.setSystemPrompt(req.getSystemPrompt());
        entity.setModel(req.getModel() != null ? req.getModel() : "MiniMax-M2.5-highspeed");
        entity.setTemperature(req.getTemperature());
        entity.setMaxTokens(req.getMaxTokens() != null ? req.getMaxTokens() : 2000);
        entity.setStatus(req.getStatus() != null ? req.getStatus() : 1);
        entity.setIsPublic(req.getIsPublic() != null ? req.getIsPublic() : 0);

        // tools / kbIds 序列化为 JSON 字符串
        try {
            entity.setTools(req.getTools() != null
                    ? objectMapper.writeValueAsString(req.getTools())
                    : null);
            entity.setKbIds(req.getKbIds() != null
                    ? objectMapper.writeValueAsString(req.getKbIds())
                    : null);
        } catch (JsonProcessingException e) {
            throw new BizException(ResultCode.PARAM_ERROR, "tools/kbIds 序列化失败");
        }
        return entity;
    }

    @SuppressWarnings("unchecked")
    private AgentConfigVO toVO(AgentConfig entity) {
        AgentConfigVO vo = new AgentConfigVO();
        vo.setId(entity.getId());
        vo.setTenantId(entity.getTenantId());
        vo.setName(entity.getName());
        vo.setDescription(entity.getDescription());
        vo.setAvatar(entity.getAvatar());
        vo.setSystemPrompt(entity.getSystemPrompt());
        vo.setModel(entity.getModel());
        vo.setTemperature(entity.getTemperature());
        vo.setMaxTokens(entity.getMaxTokens());
        vo.setVersion(entity.getVersion());
        vo.setStatus(entity.getStatus());
        vo.setIsPublic(entity.getIsPublic());
        vo.setCreateTime(entity.getCreateTime());
        vo.setUpdateTime(entity.getUpdateTime());

        // 反序列化 JSON 字符串
        try {
            if (StringUtils.hasText(entity.getTools())) {
                vo.setTools(objectMapper.readValue(entity.getTools(), List.class));
            } else {
                vo.setTools(Collections.emptyList());
            }
            if (StringUtils.hasText(entity.getKbIds())) {
                List<Number> ids = objectMapper.readValue(entity.getKbIds(), List.class);
                vo.setKbIds(ids.stream().map(Number::longValue).collect(Collectors.toList()));
            } else {
                vo.setKbIds(Collections.emptyList());
            }
        } catch (JsonProcessingException e) {
            log.warn("Failed to deserialize tools/kbIds for agent[{}]", entity.getId());
            vo.setTools(Collections.emptyList());
            vo.setKbIds(Collections.emptyList());
        }
        return vo;
    }
}
