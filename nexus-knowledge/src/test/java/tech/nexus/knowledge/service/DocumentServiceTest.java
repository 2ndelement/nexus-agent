package tech.nexus.knowledge.service;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;
import tech.nexus.common.exception.BizException;
import tech.nexus.knowledge.dto.CreateKbRequest;
import tech.nexus.knowledge.dto.DocumentVO;
import tech.nexus.knowledge.dto.GrantPermissionRequest;
import tech.nexus.knowledge.dto.KnowledgeBaseVO;
import tech.nexus.knowledge.entity.DocumentChunk;
import tech.nexus.knowledge.service.impl.DocumentServiceImpl;
import tech.nexus.knowledge.service.impl.KnowledgeBaseServiceImpl;

import java.util.List;

import static org.assertj.core.api.Assertions.*;

/**
 * 文档管理服务测试。
 *
 * <p>使用 H2 内存数据库，文件写入 /tmp/nexus-knowledge-test-uploads。
 */
@SpringBootTest
@ActiveProfiles("test")
@Transactional
@DisplayName("DocumentService 文档上传与分片测试")
class DocumentServiceTest {

    @Autowired
    private DocumentServiceImpl documentService;

    @Autowired
    private KnowledgeBaseServiceImpl kbService;

    private static final Long TENANT = 1L;
    private static final Long USER_OWNER = 100L;
    private static final Long USER_EDITOR = 200L;
    private static final Long USER_VIEWER = 300L;
    private static final Long USER_NONE = 400L;

    private Long kbId;

    @BeforeEach
    void setUp() {
        // 创建知识库，USER_OWNER 自动获得 OWNER 权限
        CreateKbRequest req = new CreateKbRequest();
        req.setName("文档测试知识库-" + System.nanoTime());
        KnowledgeBaseVO kb = kbService.create(TENANT, USER_OWNER, req);
        kbId = kb.getId();

        // 授予 USER_EDITOR EDITOR 权限
        GrantPermissionRequest grantEditor = new GrantPermissionRequest();
        grantEditor.setUserId(USER_EDITOR);
        grantEditor.setRole("EDITOR");
        kbService.grantPermission(TENANT, USER_OWNER, kbId, grantEditor);

        // 授予 USER_VIEWER VIEWER 权限
        GrantPermissionRequest grantViewer = new GrantPermissionRequest();
        grantViewer.setUserId(USER_VIEWER);
        grantViewer.setRole("VIEWER");
        kbService.grantPermission(TENANT, USER_OWNER, kbId, grantViewer);
    }

    // ────────────────────────────────────────────────────────
    // Test-D1: 上传 TXT 文档
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("上传 TXT 文档 → status=DONE，chunkCount>0")
    void upload_txt_success() {
        String content = "Hello World! ".repeat(100); // ~1300 chars
        MockMultipartFile file = new MockMultipartFile(
                "file", "test.txt", "text/plain", content.getBytes());

        DocumentVO vo = documentService.upload(TENANT, USER_OWNER, kbId, file);

        assertThat(vo.getId()).isNotNull();
        assertThat(vo.getName()).isEqualTo("test.txt");
        assertThat(vo.getFileType()).isEqualTo("txt");
        assertThat(vo.getParseStatus()).isEqualTo("DONE");
        assertThat(vo.getChunkCount()).isPositive();
    }

    // ────────────────────────────────────────────────────────
    // Test-D2: 上传 MD 文档
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("上传 MD 文档 → 正常分片")
    void upload_md_success() {
        String content = "# Title\n\n" + "Content paragraph. ".repeat(50);
        MockMultipartFile file = new MockMultipartFile(
                "file", "readme.md", "text/markdown", content.getBytes());

        DocumentVO vo = documentService.upload(TENANT, USER_EDITOR, kbId, file);

        assertThat(vo.getParseStatus()).isEqualTo("DONE");
        assertThat(vo.getFileType()).isEqualTo("md");
        assertThat(vo.getChunkCount()).isPositive();
    }

    // ────────────────────────────────────────────────────────
    // Test-D3: VIEWER 无权上传
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("VIEWER 上传文档 → FORBIDDEN")
    void upload_viewer_forbidden() {
        MockMultipartFile file = new MockMultipartFile(
                "file", "test.txt", "text/plain", "test content".getBytes());

        assertThatThrownBy(() -> documentService.upload(TENANT, USER_VIEWER, kbId, file))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("EDITOR");
    }

    // ────────────────────────────────────────────────────────
    // Test-D4: 非法文件类型
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("上传 exe 文件 → 参数错误")
    void upload_illegal_file_type() {
        MockMultipartFile file = new MockMultipartFile(
                "file", "virus.exe", "application/octet-stream", "binary".getBytes());

        assertThatThrownBy(() -> documentService.upload(TENANT, USER_OWNER, kbId, file))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("不支持的文件类型");
    }

    // ────────────────────────────────────────────────────────
    // Test-D5: 路径穿越攻击防护
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("文件名含 ../ → 参数错误")
    void upload_path_traversal_rejected() {
        MockMultipartFile file = new MockMultipartFile(
                "file", "../etc/passwd.txt", "text/plain", "attack".getBytes());

        assertThatThrownBy(() -> documentService.upload(TENANT, USER_OWNER, kbId, file))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("非法文件名");
    }

    // ────────────────────────────────────────────────────────
    // Test-D6: 列出文档
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("上传 2 个文档后，列表返回 2 条")
    void list_documents() {
        uploadTxt("doc1.txt", "Content 1");
        uploadTxt("doc2.txt", "Content 2");

        List<DocumentVO> docs = documentService.list(TENANT, USER_VIEWER, kbId);
        assertThat(docs).hasSize(2);
    }

    // ────────────────────────────────────────────────────────
    // Test-D7: 删除文档
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("删除文档后列表为空")
    void delete_document() {
        DocumentVO vo = uploadTxt("del.txt", "To be deleted");
        documentService.delete(TENANT, USER_OWNER, kbId, vo.getId());

        List<DocumentVO> docs = documentService.list(TENANT, USER_OWNER, kbId);
        assertThat(docs).isEmpty();
    }

    // ────────────────────────────────────────────────────────
    // Test-D8: 查看分片内容
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("上传后可查看分片列表，内容正确")
    void listChunks_correct_content() {
        String content = "A".repeat(600); // 600 chars, chunkSize=500 → 2 chunks
        MockMultipartFile file = new MockMultipartFile(
                "file", "chunks.txt", "text/plain", content.getBytes());

        DocumentVO vo = documentService.upload(TENANT, USER_OWNER, kbId, file);

        List<DocumentChunk> chunks = documentService.listChunks(TENANT, USER_OWNER, kbId, vo.getId());
        assertThat(chunks).isNotEmpty();
        assertThat(chunks.get(0).getChunkIndex()).isEqualTo(0);
        // 每个分片内容不为空
        chunks.forEach(c -> assertThat(c.getContent()).isNotBlank());
    }

    // ────────────────────────────────────────────────────────
    // Test-D9: 分片逻辑单元测试
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("chunkText：500字 chunkSize=200 overlap=50 → 正确分片数")
    void chunkText_logic() {
        String text = "X".repeat(500);
        List<String> chunks = documentService.chunkText(text, 200, 50);

        // step = 200-50=150, first chunk: 0-200, second: 150-350, third: 300-500
        assertThat(chunks).hasSizeGreaterThanOrEqualTo(3);
        assertThat(chunks.get(0)).hasSize(200);
        // 最后一个分片内容不超过 chunkSize
        assertThat(chunks.get(chunks.size() - 1).length()).isLessThanOrEqualTo(200);
    }

    // ────────────────────────────────────────────────────────
    // Test-D10: 无权限用户无法查看文档列表
    // ────────────────────────────────────────────────────────

    @Test
    @DisplayName("无权限用户查看文档列表 → FORBIDDEN")
    void list_no_permission_forbidden() {
        assertThatThrownBy(() -> documentService.list(TENANT, USER_NONE, kbId))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("无权访问");
    }

    // ────────────────────────────────────────────────────────
    // Helper
    // ────────────────────────────────────────────────────────

    private DocumentVO uploadTxt(String filename, String content) {
        MockMultipartFile file = new MockMultipartFile(
                "file", filename, "text/plain", content.getBytes());
        return documentService.upload(TENANT, USER_OWNER, kbId, file);
    }
}
