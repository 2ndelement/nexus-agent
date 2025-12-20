package tech.nexus.knowledge.service;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.PageResult;
import tech.nexus.knowledge.dto.*;
import tech.nexus.knowledge.service.impl.KnowledgeBaseServiceImpl;

import java.util.List;

import static org.assertj.core.api.Assertions.*;

/**
 * KnowledgeBaseService 服务层测试。
 *
 * <p>使用 H2 内存数据库，无 Redis 依赖。
 */
@SpringBootTest
@ActiveProfiles("test")
@Transactional
@DisplayName("KnowledgeBaseService 服务层测试")
class KnowledgeBaseServiceTest {

    @Autowired
    private KnowledgeBaseServiceImpl kbService;

    private static final Long TENANT_A = 1L;
    private static final Long TENANT_B = 2L;
    private static final Long USER_1 = 100L;
    private static final Long USER_2 = 200L;
    private static final Long USER_3 = 300L;

    // ─── 创建知识库 ───────────────────────────────────────────────────────────

    @Test
    @DisplayName("创建知识库 → 返回 ID，类型默认 GENERAL")
    void create_returns_id_with_defaults() {
        CreateKbRequest req = new CreateKbRequest();
        req.setName("测试知识库");
        req.setDescription("用于单元测试");

        KnowledgeBaseVO vo = kbService.create(TENANT_A, USER_1, req);

        assertThat(vo.getId()).isNotNull().isPositive();
        assertThat(vo.getName()).isEqualTo("测试知识库");
        assertThat(vo.getType()).isEqualTo("GENERAL");
        assertThat(vo.getEmbedModel()).isEqualTo("sentence-transformers");
        assertThat(vo.getStatus()).isEqualTo(1);
        assertThat(vo.getDocCount()).isEqualTo(0);
        assertThat(vo.getTenantId()).isEqualTo(TENANT_A);
    }

    @Test
    @DisplayName("创建知识库 → 创建者自动获得 OWNER 权限")
    void create_grants_owner_permission_to_creator() {
        CreateKbRequest req = new CreateKbRequest();
        req.setName("OWNER权限测试");

        KnowledgeBaseVO vo = kbService.create(TENANT_A, USER_1, req);

        // USER_1 应有 OWNER 权限（能查看权限列表）
        List<KbPermissionVO> permissions = kbService.listPermissions(TENANT_A, USER_1, vo.getId());
        assertThat(permissions).hasSize(1);
        assertThat(permissions.get(0).getRole()).isEqualTo("OWNER");
        assertThat(permissions.get(0).getUserId()).isEqualTo(USER_1);
    }

    @Test
    @DisplayName("同租户下知识库名称重复 → 抛 BizException PARAM_ERROR")
    void create_duplicate_name_throws() {
        CreateKbRequest req = new CreateKbRequest();
        req.setName("重复名称");
        kbService.create(TENANT_A, USER_1, req);

        CreateKbRequest req2 = new CreateKbRequest();
        req2.setName("重复名称");
        assertThatThrownBy(() -> kbService.create(TENANT_A, USER_2, req2))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("知识库名称已存在");
    }

    @Test
    @DisplayName("不同租户可以有同名知识库")
    void create_same_name_different_tenant_ok() {
        CreateKbRequest req = new CreateKbRequest();
        req.setName("同名知识库");

        KnowledgeBaseVO voA = kbService.create(TENANT_A, USER_1, req);
        KnowledgeBaseVO voB = kbService.create(TENANT_B, USER_2, req);

        assertThat(voA.getId()).isNotEqualTo(voB.getId());
    }

    // ─── 多租户隔离 ───────────────────────────────────────────────────────────

    @Test
    @DisplayName("租户A的知识库不能被租户B查询")
    void get_cross_tenant_throws_not_found() {
        CreateKbRequest req = new CreateKbRequest();
        req.setName("租户A的库");
        KnowledgeBaseVO vo = kbService.create(TENANT_A, USER_1, req);

        // 租户B用相同ID查询 → NOT_FOUND
        assertThatThrownBy(() -> kbService.getById(TENANT_B, vo.getId()))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("知识库不存在");
    }

    @Test
    @DisplayName("列表只返回有权限的知识库")
    void list_only_returns_permitted_kbs() {
        // USER_1 创建2个库
        CreateKbRequest r1 = new CreateKbRequest();
        r1.setName("库1");
        CreateKbRequest r2 = new CreateKbRequest();
        r2.setName("库2");
        KnowledgeBaseVO kb1 = kbService.create(TENANT_A, USER_1, r1);
        kbService.create(TENANT_A, USER_1, r2);

        // USER_2 没有任何权限 → 空列表
        PageResult<KnowledgeBaseVO> result2 = kbService.list(TENANT_A, USER_2, 1, 20);
        assertThat(result2.getRecords()).isEmpty();

        // USER_1 有2个权限 → 返回2个
        PageResult<KnowledgeBaseVO> result1 = kbService.list(TENANT_A, USER_1, 1, 20);
        assertThat(result1.getRecords()).hasSize(2);
    }

    // ─── 权限管理 ─────────────────────────────────────────────────────────────

    @Test
    @DisplayName("授予 EDITOR 权限 → 目标用户可查看权限列表")
    void grant_editor_permission() {
        CreateKbRequest req = new CreateKbRequest();
        req.setName("权限测试库");
        KnowledgeBaseVO vo = kbService.create(TENANT_A, USER_1, req);

        GrantPermissionRequest grant = new GrantPermissionRequest();
        grant.setUserId(USER_2);
        grant.setRole("EDITOR");
        kbService.grantPermission(TENANT_A, USER_1, vo.getId(), grant);

        // USER_2 现在可以查看权限列表
        List<KbPermissionVO> permissions = kbService.listPermissions(TENANT_A, USER_2, vo.getId());
        assertThat(permissions).hasSize(2); // OWNER + EDITOR
        assertThat(permissions).anyMatch(p -> p.getUserId().equals(USER_2) && "EDITOR".equals(p.getRole()));
    }

    @Test
    @DisplayName("授予权限幂等：重复授权更新角色")
    void grant_permission_idempotent_updates_role() {
        CreateKbRequest req = new CreateKbRequest();
        req.setName("幂等测试库");
        KnowledgeBaseVO vo = kbService.create(TENANT_A, USER_1, req);

        GrantPermissionRequest grant = new GrantPermissionRequest();
        grant.setUserId(USER_2);
        grant.setRole("VIEWER");
        kbService.grantPermission(TENANT_A, USER_1, vo.getId(), grant);

        // 更新为 EDITOR
        grant.setRole("EDITOR");
        kbService.grantPermission(TENANT_A, USER_1, vo.getId(), grant);

        List<KbPermissionVO> permissions = kbService.listPermissions(TENANT_A, USER_1, vo.getId());
        assertThat(permissions).anyMatch(p -> p.getUserId().equals(USER_2) && "EDITOR".equals(p.getRole()));
        // 不应产生重复记录
        long count = permissions.stream().filter(p -> p.getUserId().equals(USER_2)).count();
        assertThat(count).isEqualTo(1);
    }

    @Test
    @DisplayName("VIEWER 无权授予他人权限 → 抛 FORBIDDEN")
    void viewer_cannot_grant_permission() {
        CreateKbRequest req = new CreateKbRequest();
        req.setName("权限校验库");
        KnowledgeBaseVO vo = kbService.create(TENANT_A, USER_1, req);

        // 授予 USER_2 VIEWER
        GrantPermissionRequest grantViewer = new GrantPermissionRequest();
        grantViewer.setUserId(USER_2);
        grantViewer.setRole("VIEWER");
        kbService.grantPermission(TENANT_A, USER_1, vo.getId(), grantViewer);

        // USER_2 (VIEWER) 尝试授予 USER_3 权限 → FORBIDDEN
        GrantPermissionRequest grantOther = new GrantPermissionRequest();
        grantOther.setUserId(USER_3);
        grantOther.setRole("VIEWER");
        assertThatThrownBy(() -> kbService.grantPermission(TENANT_A, USER_2, vo.getId(), grantOther))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("OWNER");
    }

    @Test
    @DisplayName("无权限用户访问知识库 → 抛 FORBIDDEN")
    void no_permission_user_throws_forbidden() {
        CreateKbRequest req = new CreateKbRequest();
        req.setName("无权限测试");
        KnowledgeBaseVO vo = kbService.create(TENANT_A, USER_1, req);

        // USER_2 无权限，尝试查看权限列表
        assertThatThrownBy(() -> kbService.listPermissions(TENANT_A, USER_2, vo.getId()))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("无权访问");
    }

    @Test
    @DisplayName("撤销权限后，用户无法访问知识库")
    void revoke_permission_denies_access() {
        CreateKbRequest req = new CreateKbRequest();
        req.setName("撤销测试");
        KnowledgeBaseVO vo = kbService.create(TENANT_A, USER_1, req);

        // 授予 USER_2 VIEWER
        GrantPermissionRequest grant = new GrantPermissionRequest();
        grant.setUserId(USER_2);
        grant.setRole("VIEWER");
        kbService.grantPermission(TENANT_A, USER_1, vo.getId(), grant);

        // 撤销
        kbService.revokePermission(TENANT_A, USER_1, vo.getId(), USER_2);

        // USER_2 再次访问 → FORBIDDEN
        assertThatThrownBy(() -> kbService.listPermissions(TENANT_A, USER_2, vo.getId()))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("无权访问");
    }

    // ─── 更新分片配置 ──────────────────────────────────────────────────────────

    @Test
    @DisplayName("EDITOR 可以更新分片配置")
    void editor_can_update_chunk_config() {
        CreateKbRequest req = new CreateKbRequest();
        req.setName("分片配置测试");
        KnowledgeBaseVO vo = kbService.create(TENANT_A, USER_1, req);

        // 授予 USER_2 EDITOR
        GrantPermissionRequest grant = new GrantPermissionRequest();
        grant.setUserId(USER_2);
        grant.setRole("EDITOR");
        kbService.grantPermission(TENANT_A, USER_1, vo.getId(), grant);

        UpdateChunkConfigRequest chunkReq = new UpdateChunkConfigRequest();
        chunkReq.setChunkSize(600);
        chunkReq.setChunkOverlap(80);
        chunkReq.setSplitBy("paragraph");

        KnowledgeBaseVO updated = kbService.updateChunkConfig(TENANT_A, USER_2, vo.getId(), chunkReq);
        assertThat(updated.getChunkConfig()).contains("600");
        assertThat(updated.getChunkConfig()).contains("paragraph");
    }

    @Test
    @DisplayName("VIEWER 无法更新分片配置 → 抛 FORBIDDEN")
    void viewer_cannot_update_chunk_config() {
        CreateKbRequest req = new CreateKbRequest();
        req.setName("分片权限测试");
        KnowledgeBaseVO vo = kbService.create(TENANT_A, USER_1, req);

        GrantPermissionRequest grant = new GrantPermissionRequest();
        grant.setUserId(USER_2);
        grant.setRole("VIEWER");
        kbService.grantPermission(TENANT_A, USER_1, vo.getId(), grant);

        UpdateChunkConfigRequest chunkReq = new UpdateChunkConfigRequest();
        chunkReq.setChunkSize(300);

        assertThatThrownBy(() -> kbService.updateChunkConfig(TENANT_A, USER_2, vo.getId(), chunkReq))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("EDITOR");
    }

    // ─── 删除知识库 ────────────────────────────────────────────────────────────

    @Test
    @DisplayName("删除知识库后，查询返回 NOT_FOUND")
    void delete_then_get_throws_not_found() {
        CreateKbRequest req = new CreateKbRequest();
        req.setName("待删除库");
        KnowledgeBaseVO vo = kbService.create(TENANT_A, USER_1, req);

        kbService.delete(TENANT_A, USER_1, vo.getId());

        assertThatThrownBy(() -> kbService.getById(TENANT_A, vo.getId()))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("知识库不存在");
    }

    @Test
    @DisplayName("EDITOR 无法删除知识库 → 抛 FORBIDDEN")
    void editor_cannot_delete_kb() {
        CreateKbRequest req = new CreateKbRequest();
        req.setName("删除权限测试");
        KnowledgeBaseVO vo = kbService.create(TENANT_A, USER_1, req);

        GrantPermissionRequest grant = new GrantPermissionRequest();
        grant.setUserId(USER_2);
        grant.setRole("EDITOR");
        kbService.grantPermission(TENANT_A, USER_1, vo.getId(), grant);

        assertThatThrownBy(() -> kbService.delete(TENANT_A, USER_2, vo.getId()))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("OWNER");
    }

    // ─── Agent 绑定 ───────────────────────────────────────────────────────────

    @Test
    @DisplayName("绑定 Agent 幂等：重复绑定不报错")
    void bind_agent_idempotent() {
        CreateKbRequest req = new CreateKbRequest();
        req.setName("绑定测试库");
        KnowledgeBaseVO vo = kbService.create(TENANT_A, USER_1, req);

        kbService.bindAgent(TENANT_A, vo.getId(), 999L);
        // 再次绑定不应抛异常
        assertThatCode(() -> kbService.bindAgent(TENANT_A, vo.getId(), 999L))
                .doesNotThrowAnyException();
    }
}
