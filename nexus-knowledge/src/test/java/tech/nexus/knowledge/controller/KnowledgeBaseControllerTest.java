package tech.nexus.knowledge.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.ResultCode;
import tech.nexus.knowledge.dto.*;
import tech.nexus.knowledge.service.impl.KnowledgeBaseServiceImpl;

import java.time.LocalDateTime;
import java.util.List;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * KnowledgeBaseController 控制器层测试。
 * KnowledgeBaseServiceImpl 全部 Mock。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DisplayName("KnowledgeBaseController 控制器层测试")
class KnowledgeBaseControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private KnowledgeBaseServiceImpl kbService;

    private static final String BASE_URL = "/api/knowledge/bases";
    private static final String TENANT_HEADER = "X-Tenant-Id";
    private static final String USER_HEADER = "X-User-Id";

    private KnowledgeBaseVO mockKbVO(Long id) {
        return KnowledgeBaseVO.builder()
                .id(id)
                .tenantId(1L)
                .name("测试知识库")
                .type("GENERAL")
                .embedModel("sentence-transformers")
                .status(1)
                .docCount(0)
                .createTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .build();
    }

    // ─── POST /bases 创建 ─────────────────────────────────────────────────────

    @Test
    @DisplayName("POST /bases 正常创建 → 200 + id")
    void create_success() throws Exception {
        when(kbService.create(eq(1L), eq(100L), any())).thenReturn(mockKbVO(1L));

        CreateKbRequest req = new CreateKbRequest();
        req.setName("测试知识库");

        mockMvc.perform(post(BASE_URL)
                        .header(TENANT_HEADER, "1")
                        .header(USER_HEADER, "100")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.id").value(1))
                .andExpect(jsonPath("$.data.name").value("测试知识库"));
    }

    @Test
    @DisplayName("POST /bases 缺少 name → 400 参数校验错误")
    void create_missing_name_returns_400() throws Exception {
        String json = "{}";

        mockMvc.perform(post(BASE_URL)
                        .header(TENANT_HEADER, "1")
                        .header(USER_HEADER, "100")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(400));
    }

    @Test
    @DisplayName("POST /bases 知识库名称重复 → 400")
    void create_duplicate_name_returns_400() throws Exception {
        when(kbService.create(any(), any(), any()))
                .thenThrow(new BizException(ResultCode.PARAM_ERROR, "知识库名称已存在"));

        CreateKbRequest req = new CreateKbRequest();
        req.setName("重复名称");

        mockMvc.perform(post(BASE_URL)
                        .header(TENANT_HEADER, "1")
                        .header(USER_HEADER, "100")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(400))
                .andExpect(jsonPath("$.msg").value("知识库名称已存在"));
    }

    // ─── GET /bases 列表 ──────────────────────────────────────────────────────

    @Test
    @DisplayName("GET /bases 返回分页列表 → 200")
    void list_success() throws Exception {
        tech.nexus.common.result.PageResult<KnowledgeBaseVO> pageResult =
                tech.nexus.common.result.PageResult.of(List.of(mockKbVO(1L)), 1L, 1, 20);
        when(kbService.list(eq(1L), eq(100L), eq(1), eq(20))).thenReturn(pageResult);

        mockMvc.perform(get(BASE_URL)
                        .header(TENANT_HEADER, "1")
                        .header(USER_HEADER, "100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.total").value(1));
    }

    // ─── GET /bases/{id} 详情 ─────────────────────────────────────────────────

    @Test
    @DisplayName("GET /bases/{id} 获取知识库详情 → 200")
    void get_success() throws Exception {
        when(kbService.getById(eq(1L), eq(1L))).thenReturn(mockKbVO(1L));

        mockMvc.perform(get(BASE_URL + "/1")
                        .header(TENANT_HEADER, "1")
                        .header(USER_HEADER, "100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.id").value(1));
    }

    @Test
    @DisplayName("GET /bases/{id} 不存在 → 404")
    void get_not_found_returns_404() throws Exception {
        when(kbService.getById(any(), any()))
                .thenThrow(new BizException(ResultCode.NOT_FOUND, "知识库不存在"));

        mockMvc.perform(get(BASE_URL + "/999")
                        .header(TENANT_HEADER, "1")
                        .header(USER_HEADER, "100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(404));
    }

    // ─── DELETE /bases/{id} 删除 ──────────────────────────────────────────────

    @Test
    @DisplayName("DELETE /bases/{id} 正常删除 → 200")
    void delete_success() throws Exception {
        doNothing().when(kbService).delete(eq(1L), eq(100L), eq(1L));

        mockMvc.perform(delete(BASE_URL + "/1")
                        .header(TENANT_HEADER, "1")
                        .header(USER_HEADER, "100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));
    }

    @Test
    @DisplayName("DELETE /bases/{id} 权限不足 → 403")
    void delete_forbidden_returns_403() throws Exception {
        doThrow(new BizException(ResultCode.FORBIDDEN, "权限不足，需要 OWNER 角色"))
                .when(kbService).delete(any(), any(), any());

        mockMvc.perform(delete(BASE_URL + "/1")
                        .header(TENANT_HEADER, "1")
                        .header(USER_HEADER, "200"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(403));
    }

    // ─── PUT /bases/{id}/chunk-config 分片配置 ─────────────────────────────────

    @Test
    @DisplayName("PUT /bases/{id}/chunk-config 更新分片配置 → 200")
    void updateChunkConfig_success() throws Exception {
        KnowledgeBaseVO updated = mockKbVO(1L);
        updated.setChunkConfig("{\"chunkSize\":600,\"chunkOverlap\":80,\"splitBy\":\"paragraph\"}");
        when(kbService.updateChunkConfig(eq(1L), eq(100L), eq(1L), any())).thenReturn(updated);

        UpdateChunkConfigRequest req = new UpdateChunkConfigRequest();
        req.setChunkSize(600);
        req.setChunkOverlap(80);
        req.setSplitBy("paragraph");

        mockMvc.perform(put(BASE_URL + "/1/chunk-config")
                        .header(TENANT_HEADER, "1")
                        .header(USER_HEADER, "100")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.chunkConfig").isNotEmpty());
    }

    @Test
    @DisplayName("PUT /bases/{id}/chunk-config 缺少 chunkSize → 400")
    void updateChunkConfig_missing_chunkSize_returns_400() throws Exception {
        String json = "{\"chunkOverlap\":50}";

        mockMvc.perform(put(BASE_URL + "/1/chunk-config")
                        .header(TENANT_HEADER, "1")
                        .header(USER_HEADER, "100")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(400));
    }

    // ─── POST /bases/{id}/permissions 授予权限 ─────────────────────────────────

    @Test
    @DisplayName("POST /bases/{id}/permissions 授予 EDITOR 权限 → 200")
    void grantPermission_success() throws Exception {
        KbPermissionVO permVO = KbPermissionVO.builder()
                .id(1L).kbId(1L).userId(200L).role("EDITOR")
                .createTime(LocalDateTime.now()).build();
        when(kbService.grantPermission(eq(1L), eq(100L), eq(1L), any())).thenReturn(permVO);

        GrantPermissionRequest req = new GrantPermissionRequest();
        req.setUserId(200L);
        req.setRole("EDITOR");

        mockMvc.perform(post(BASE_URL + "/1/permissions")
                        .header(TENANT_HEADER, "1")
                        .header(USER_HEADER, "100")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.role").value("EDITOR"));
    }

    @Test
    @DisplayName("POST /bases/{id}/permissions 无效角色 → 400")
    void grantPermission_invalid_role_returns_400() throws Exception {
        GrantPermissionRequest req = new GrantPermissionRequest();
        req.setUserId(200L);
        req.setRole("SUPERADMIN"); // 无效角色

        mockMvc.perform(post(BASE_URL + "/1/permissions")
                        .header(TENANT_HEADER, "1")
                        .header(USER_HEADER, "100")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(400));
    }

    // ─── GET /bases/{id}/permissions 权限列表 ─────────────────────────────────

    @Test
    @DisplayName("GET /bases/{id}/permissions 返回权限列表 → 200")
    void listPermissions_success() throws Exception {
        List<KbPermissionVO> permissions = List.of(
                KbPermissionVO.builder().id(1L).kbId(1L).userId(100L).role("OWNER")
                        .createTime(LocalDateTime.now()).build()
        );
        when(kbService.listPermissions(eq(1L), eq(100L), eq(1L))).thenReturn(permissions);

        mockMvc.perform(get(BASE_URL + "/1/permissions")
                        .header(TENANT_HEADER, "1")
                        .header(USER_HEADER, "100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data").isArray())
                .andExpect(jsonPath("$.data[0].role").value("OWNER"));
    }

    // ─── Agent 绑定 ───────────────────────────────────────────────────────────

    @Test
    @DisplayName("POST /bases/{id}/bind/{agentId} 绑定 Agent → 200")
    void bindAgent_success() throws Exception {
        doNothing().when(kbService).bindAgent(eq(1L), eq(1L), eq(999L));

        mockMvc.perform(post(BASE_URL + "/1/bind/999")
                        .header(TENANT_HEADER, "1")
                        .header(USER_HEADER, "100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));
    }

    @Test
    @DisplayName("DELETE /bases/{id}/bind/{agentId} 解绑 Agent → 200")
    void unbindAgent_success() throws Exception {
        doNothing().when(kbService).unbindAgent(eq(1L), eq(1L), eq(999L));

        mockMvc.perform(delete(BASE_URL + "/1/bind/999")
                        .header(TENANT_HEADER, "1")
                        .header(USER_HEADER, "100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));
    }
}
