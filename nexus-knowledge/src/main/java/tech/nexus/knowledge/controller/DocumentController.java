package tech.nexus.knowledge.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import tech.nexus.common.result.Result;
import tech.nexus.knowledge.dto.DocumentVO;
import tech.nexus.knowledge.entity.DocumentChunk;
import tech.nexus.knowledge.service.DocumentService;

import java.util.List;

/**
 * 文档管理控制器。
 *
 * <pre>
 * POST   /api/knowledge/bases/{kbId}/documents              上传文档（multipart）
 * GET    /api/knowledge/bases/{kbId}/documents              文档列表
 * DELETE /api/knowledge/bases/{kbId}/documents/{docId}      删除文档
 * GET    /api/knowledge/bases/{kbId}/documents/{docId}/chunks  查看分片
 * </pre>
 */
@RestController
@RequestMapping("/api/knowledge/bases/{kbId}/documents")
@RequiredArgsConstructor
public class DocumentController {

    private final DocumentService documentService;

    /** 上传文档（txt/md/pdf/docx，≤50MB） */
    @PostMapping(consumes = "multipart/form-data")
    public Result<DocumentVO> upload(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long kbId,
            @RequestPart("file") MultipartFile file) {
        return Result.success(documentService.upload(tenantId, userId, kbId, file));
    }

    /** 列出文档 */
    @GetMapping
    public Result<List<DocumentVO>> list(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long kbId) {
        return Result.success(documentService.list(tenantId, userId, kbId));
    }

    /** 删除文档 */
    @DeleteMapping("/{docId}")
    public Result<Void> delete(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long kbId,
            @PathVariable Long docId) {
        documentService.delete(tenantId, userId, kbId, docId);
        return Result.success();
    }

    /** 查看文档分片 */
    @GetMapping("/{docId}/chunks")
    public Result<List<DocumentChunk>> listChunks(
            @RequestHeader("X-Tenant-Id") Long tenantId,
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long kbId,
            @PathVariable Long docId) {
        return Result.success(documentService.listChunks(tenantId, userId, kbId, docId));
    }
}
