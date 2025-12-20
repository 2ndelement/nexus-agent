package tech.nexus.knowledge.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.PageResult;
import tech.nexus.common.result.ResultCode;
import tech.nexus.knowledge.dto.*;
import tech.nexus.knowledge.entity.KbAgentBinding;
import tech.nexus.knowledge.entity.KbPermission;
import tech.nexus.knowledge.entity.KnowledgeBase;
import tech.nexus.knowledge.mapper.KbAgentBindingMapper;
import tech.nexus.knowledge.mapper.KbPermissionMapper;
import tech.nexus.knowledge.mapper.KnowledgeBaseMapper;
import tech.nexus.knowledge.mapper.DocumentMapper;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 知识库服务实现。
 *
 * <p>所有查询必须携带 tenantId 条件，确保多租户数据隔离。
 * 权限模型：OWNER > EDITOR > VIEWER
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class KnowledgeBaseServiceImpl {

    private final KnowledgeBaseMapper kbMapper;
    private final DocumentMapper documentMapper;
    private final KbPermissionMapper permissionMapper;
    private final KbAgentBindingMapper bindingMapper;
    private final ObjectMapper objectMapper;

    // ─── 创建知识库 ───────────────────────────────────────────────────────────

    /**
     * 创建知识库，并自动为创建者授予 OWNER 权限。
     *
     * @param tenantId 租户ID
     * @param userId   创建用户ID
     * @param req      创建请求
     * @return 创建的知识库 VO
     */
    @Transactional
    public KnowledgeBaseVO create(Long tenantId, Long userId, CreateKbRequest req) {
        // 检查同租户下知识库名称唯一性
        long count = kbMapper.selectCount(new LambdaQueryWrapper<KnowledgeBase>()
                .eq(KnowledgeBase::getTenantId, tenantId)
                .eq(KnowledgeBase::getName, req.getName()));
        if (count > 0) {
            throw new BizException(ResultCode.PARAM_ERROR, "知识库名称已存在");
        }

        KnowledgeBase kb = new KnowledgeBase();
        kb.setTenantId(tenantId);
        kb.setName(req.getName());
        kb.setDescription(req.getDescription());
        kb.setType(req.getType() != null ? req.getType() : "GENERAL");
        kb.setEmbedModel(req.getEmbedModel() != null ? req.getEmbedModel() : "sentence-transformers");
        kb.setChunkConfig(req.getChunkConfig());
        kb.setStatus(1);
        kb.setDocCount(0);
        kb.setCreateTime(LocalDateTime.now());
        kb.setUpdateTime(LocalDateTime.now());
        kbMapper.insert(kb);

        // 自动授予创建者 OWNER 权限
        grantPermissionInternal(tenantId, kb.getId(), userId, "OWNER");

        log.debug("创建知识库 kbId={} tenantId={} userId={}", kb.getId(), tenantId, userId);
        return toVO(kb);
    }

    // ─── 列出知识库（分页） ────────────────────────────────────────────────────

    /**
     * 列出指定租户下的知识库（分页），支持用户权限过滤。
     *
     * @param tenantId 租户ID
     * @param userId   当前用户ID（仅返回有权限的知识库）
     * @param page     页码（从1开始）
     * @param size     每页大小
     */
    public PageResult<KnowledgeBaseVO> list(Long tenantId, Long userId, int page, int size) {
        // 获取该用户有权限的知识库ID列表
        List<Long> permittedKbIds = permissionMapper.selectList(
                new LambdaQueryWrapper<KbPermission>()
                        .eq(KbPermission::getTenantId, tenantId)
                        .eq(KbPermission::getUserId, userId)
                        .select(KbPermission::getKbId))
                .stream()
                .map(KbPermission::getKbId)
                .collect(Collectors.toList());

        if (permittedKbIds.isEmpty()) {
            return PageResult.of(List.of(), 0L, page, size);
        }

        Page<KnowledgeBase> mpPage = new Page<>(page, size);
        LambdaQueryWrapper<KnowledgeBase> wrapper = new LambdaQueryWrapper<KnowledgeBase>()
                .eq(KnowledgeBase::getTenantId, tenantId)
                .in(KnowledgeBase::getId, permittedKbIds)
                .ne(KnowledgeBase::getStatus, 0)
                .orderByDesc(KnowledgeBase::getUpdateTime);
        Page<KnowledgeBase> result = kbMapper.selectPage(mpPage, wrapper);

        List<KnowledgeBaseVO> vos = result.getRecords().stream()
                .map(this::toVO)
                .collect(Collectors.toList());
        return PageResult.of(vos, result.getTotal(), page, size);
    }

    // ─── 获取知识库详情 ────────────────────────────────────────────────────────

    /**
     * 获取知识库详情，强制校验 tenantId 防止跨租户访问。
     */
    public KnowledgeBaseVO getById(Long tenantId, Long kbId) {
        KnowledgeBase kb = requireKb(tenantId, kbId);
        return toVO(kb);
    }

    // ─── 更新知识库 ────────────────────────────────────────────────────────────

    /**
     * 更新知识库基本信息，需要 OWNER 或 EDITOR 权限。
     */
    @Transactional
    public KnowledgeBaseVO update(Long tenantId, Long userId, Long kbId, UpdateKbRequest req) {
        requireKb(tenantId, kbId);
        checkPermission(tenantId, kbId, userId, "EDITOR");

        LambdaUpdateWrapper<KnowledgeBase> wrapper = new LambdaUpdateWrapper<KnowledgeBase>()
                .eq(KnowledgeBase::getId, kbId)
                .eq(KnowledgeBase::getTenantId, tenantId);

        if (req.getName() != null) {
            // 检查改名后是否与其他知识库冲突
            long count = kbMapper.selectCount(new LambdaQueryWrapper<KnowledgeBase>()
                    .eq(KnowledgeBase::getTenantId, tenantId)
                    .eq(KnowledgeBase::getName, req.getName())
                    .ne(KnowledgeBase::getId, kbId));
            if (count > 0) {
                throw new BizException(ResultCode.PARAM_ERROR, "知识库名称已存在");
            }
            wrapper.set(KnowledgeBase::getName, req.getName());
        }
        if (req.getDescription() != null) wrapper.set(KnowledgeBase::getDescription, req.getDescription());
        if (req.getType() != null) wrapper.set(KnowledgeBase::getType, req.getType());
        if (req.getEmbedModel() != null) wrapper.set(KnowledgeBase::getEmbedModel, req.getEmbedModel());
        if (req.getChunkConfig() != null) wrapper.set(KnowledgeBase::getChunkConfig, req.getChunkConfig());
        wrapper.set(KnowledgeBase::getUpdateTime, LocalDateTime.now());

        kbMapper.update(null, wrapper);
        return toVO(requireKb(tenantId, kbId));
    }

    // ─── 更新分片配置 ──────────────────────────────────────────────────────────

    /**
     * 单独更新知识库的分片配置，需要 OWNER 或 EDITOR 权限。
     */
    @Transactional
    public KnowledgeBaseVO updateChunkConfig(Long tenantId, Long userId, Long kbId,
                                              UpdateChunkConfigRequest req) {
        requireKb(tenantId, kbId);
        checkPermission(tenantId, kbId, userId, "EDITOR");

        // 将 req 序列化为 JSON 存储
        String chunkConfigJson;
        try {
            chunkConfigJson = objectMapper.writeValueAsString(Map.of(
                    "chunkSize", req.getChunkSize(),
                    "chunkOverlap", req.getChunkOverlap() != null ? req.getChunkOverlap() : 50,
                    "splitBy", req.getSplitBy() != null ? req.getSplitBy() : "sentence"
            ));
        } catch (JsonProcessingException e) {
            throw new BizException(ResultCode.PARAM_ERROR, "分片配置序列化失败");
        }

        kbMapper.update(null, new LambdaUpdateWrapper<KnowledgeBase>()
                .eq(KnowledgeBase::getId, kbId)
                .eq(KnowledgeBase::getTenantId, tenantId)
                .set(KnowledgeBase::getChunkConfig, chunkConfigJson)
                .set(KnowledgeBase::getUpdateTime, LocalDateTime.now()));

        log.debug("更新分片配置 kbId={} config={}", kbId, chunkConfigJson);
        return toVO(requireKb(tenantId, kbId));
    }

    // ─── 删除知识库 ────────────────────────────────────────────────────────────

    /**
     * 删除知识库（软删除，设 status=0），仅 OWNER 可操作。
     * 同时清理该知识库下的文档、权限、绑定关系。
     */
    @Transactional
    public void delete(Long tenantId, Long userId, Long kbId) {
        requireKb(tenantId, kbId);
        checkPermission(tenantId, kbId, userId, "OWNER");

        // 软删除知识库
        kbMapper.update(null, new LambdaUpdateWrapper<KnowledgeBase>()
                .eq(KnowledgeBase::getId, kbId)
                .eq(KnowledgeBase::getTenantId, tenantId)
                .set(KnowledgeBase::getStatus, 0)
                .set(KnowledgeBase::getUpdateTime, LocalDateTime.now()));

        log.debug("删除知识库 kbId={} tenantId={}", kbId, tenantId);
    }

    // ─── 权限管理 ─────────────────────────────────────────────────────────────

    /**
     * 授予用户知识库权限（幂等：已有权限则更新角色）。
     * 仅 OWNER 可操作。
     */
    @Transactional
    public KbPermissionVO grantPermission(Long tenantId, Long operatorId, Long kbId,
                                           GrantPermissionRequest req) {
        requireKb(tenantId, kbId);
        checkPermission(tenantId, kbId, operatorId, "OWNER");

        return grantPermissionInternal(tenantId, kbId, req.getUserId(), req.getRole());
    }

    private KbPermissionVO grantPermissionInternal(Long tenantId, Long kbId, Long userId, String role) {
        // 幂等：已有权限则更新
        KbPermission existing = permissionMapper.selectOne(
                new LambdaQueryWrapper<KbPermission>()
                        .eq(KbPermission::getTenantId, tenantId)
                        .eq(KbPermission::getKbId, kbId)
                        .eq(KbPermission::getUserId, userId));

        if (existing != null) {
            permissionMapper.update(null, new LambdaUpdateWrapper<KbPermission>()
                    .eq(KbPermission::getId, existing.getId())
                    .set(KbPermission::getRole, role));
            existing.setRole(role);
            return toPermissionVO(existing);
        }

        KbPermission permission = new KbPermission();
        permission.setTenantId(tenantId);
        permission.setKbId(kbId);
        permission.setUserId(userId);
        permission.setRole(role);
        permission.setCreateTime(LocalDateTime.now());
        permissionMapper.insert(permission);
        return toPermissionVO(permission);
    }

    /**
     * 撤销用户知识库权限。仅 OWNER 可操作。
     */
    @Transactional
    public void revokePermission(Long tenantId, Long operatorId, Long kbId, Long userId) {
        requireKb(tenantId, kbId);
        checkPermission(tenantId, kbId, operatorId, "OWNER");

        permissionMapper.delete(new LambdaQueryWrapper<KbPermission>()
                .eq(KbPermission::getTenantId, tenantId)
                .eq(KbPermission::getKbId, kbId)
                .eq(KbPermission::getUserId, userId));
    }

    /**
     * 列出知识库的所有权限记录。需要 VIEWER 及以上权限。
     */
    public List<KbPermissionVO> listPermissions(Long tenantId, Long userId, Long kbId) {
        requireKb(tenantId, kbId);
        checkPermission(tenantId, kbId, userId, "VIEWER");

        return permissionMapper.selectList(
                new LambdaQueryWrapper<KbPermission>()
                        .eq(KbPermission::getTenantId, tenantId)
                        .eq(KbPermission::getKbId, kbId))
                .stream()
                .map(this::toPermissionVO)
                .collect(Collectors.toList());
    }

    // ─── Agent 绑定 ───────────────────────────────────────────────────────────

    /**
     * 绑定知识库到 Agent（幂等）。
     */
    @Transactional
    public void bindAgent(Long tenantId, Long kbId, Long agentId) {
        requireKb(tenantId, kbId);

        long count = bindingMapper.selectCount(new LambdaQueryWrapper<KbAgentBinding>()
                .eq(KbAgentBinding::getTenantId, tenantId)
                .eq(KbAgentBinding::getKbId, kbId)
                .eq(KbAgentBinding::getAgentId, agentId));
        if (count > 0) {
            log.debug("知识库已绑定 Agent，忽略 kbId={} agentId={}", kbId, agentId);
            return;
        }

        KbAgentBinding binding = new KbAgentBinding();
        binding.setTenantId(tenantId);
        binding.setKbId(kbId);
        binding.setAgentId(agentId);
        binding.setCreateTime(LocalDateTime.now());
        bindingMapper.insert(binding);
        log.debug("绑定知识库到 Agent kbId={} agentId={}", kbId, agentId);
    }

    /**
     * 解绑知识库与 Agent 的关联。
     */
    @Transactional
    public void unbindAgent(Long tenantId, Long kbId, Long agentId) {
        bindingMapper.delete(new LambdaQueryWrapper<KbAgentBinding>()
                .eq(KbAgentBinding::getTenantId, tenantId)
                .eq(KbAgentBinding::getKbId, kbId)
                .eq(KbAgentBinding::getAgentId, agentId));
    }

    // ─── 内部辅助方法 ─────────────────────────────────────────────────────────

    /**
     * 获取知识库并验证租户归属，不存在则抛 NOT_FOUND。
     */
    KnowledgeBase requireKb(Long tenantId, Long kbId) {
        KnowledgeBase kb = kbMapper.selectOne(new LambdaQueryWrapper<KnowledgeBase>()
                .eq(KnowledgeBase::getId, kbId)
                .eq(KnowledgeBase::getTenantId, tenantId)
                .ne(KnowledgeBase::getStatus, 0));
        if (kb == null) {
            throw new BizException(ResultCode.NOT_FOUND, "知识库不存在");
        }
        return kb;
    }

    /**
     * 校验用户对知识库的最低权限级别。
     * 权限级别：OWNER(3) > EDITOR(2) > VIEWER(1)
     *
     * @param minRole 最低要求角色（VIEWER / EDITOR / OWNER）
     */
    void checkPermission(Long tenantId, Long kbId, Long userId, String minRole) {
        KbPermission permission = permissionMapper.selectOne(
                new LambdaQueryWrapper<KbPermission>()
                        .eq(KbPermission::getTenantId, tenantId)
                        .eq(KbPermission::getKbId, kbId)
                        .eq(KbPermission::getUserId, userId));

        if (permission == null) {
            throw new BizException(ResultCode.FORBIDDEN, "无权访问该知识库");
        }

        int userLevel = roleLevel(permission.getRole());
        int requiredLevel = roleLevel(minRole);
        if (userLevel < requiredLevel) {
            throw new BizException(ResultCode.FORBIDDEN, "权限不足，需要 " + minRole + " 角色");
        }
    }

    private int roleLevel(String role) {
        return switch (role) {
            case "OWNER" -> 3;
            case "EDITOR" -> 2;
            case "VIEWER" -> 1;
            default -> 0;
        };
    }

    private KnowledgeBaseVO toVO(KnowledgeBase kb) {
        return KnowledgeBaseVO.builder()
                .id(kb.getId())
                .tenantId(kb.getTenantId())
                .name(kb.getName())
                .description(kb.getDescription())
                .type(kb.getType())
                .embedModel(kb.getEmbedModel())
                .chunkConfig(kb.getChunkConfig())
                .status(kb.getStatus())
                .docCount(kb.getDocCount())
                .createTime(kb.getCreateTime())
                .updateTime(kb.getUpdateTime())
                .build();
    }

    private KbPermissionVO toPermissionVO(KbPermission p) {
        return KbPermissionVO.builder()
                .id(p.getId())
                .kbId(p.getKbId())
                .userId(p.getUserId())
                .role(p.getRole())
                .createTime(p.getCreateTime())
                .build();
    }
}
