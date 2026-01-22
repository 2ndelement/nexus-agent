package tech.nexus.knowledge.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.Loader;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.ResultCode;
import tech.nexus.knowledge.dto.DocumentVO;
import tech.nexus.knowledge.entity.Document;
import tech.nexus.knowledge.entity.DocumentChunk;
import tech.nexus.knowledge.entity.KnowledgeBase;
import tech.nexus.knowledge.mapper.DocumentChunkMapper;
import tech.nexus.knowledge.mapper.DocumentMapper;
import tech.nexus.knowledge.mapper.KnowledgeBaseMapper;
import tech.nexus.knowledge.mq.EmbedTaskPublisher;
import tech.nexus.knowledge.service.DocumentService;
import tech.nexus.knowledge.service.impl.KnowledgeBaseServiceImpl;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 文档管理服务实现。
 *
 * <p>文档上传流程：
 * <ol>
 *   <li>校验文件类型（白名单）和大小（≤50MB）</li>
 *   <li>防路径穿越：文件名不允许含 ../ 或绝对路径</li>
 *   <li>保存文件到 {uploadDir}/{tenantId}/{docId}/</li>
 *   <li>插入 document 记录（PENDING）</li>
 *   <li>提取文本 → 按 chunkSize/chunkOverlap 分片 → 存 document_chunk</li>
 *   <li>更新 document 状态 DONE + chunk_count；失败则 FAILED + error_msg</li>
 *   <li>更新 knowledge_base.doc_count +1</li>
 * </ol>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DocumentServiceImpl implements DocumentService {

    private static final Set<String> ALLOWED_EXTENSIONS = Set.of("txt", "md", "pdf", "docx");
    private static final long MAX_FILE_SIZE = 50L * 1024 * 1024; // 50MB

    private final DocumentMapper documentMapper;
    private final DocumentChunkMapper chunkMapper;
    private final KnowledgeBaseMapper kbMapper;
    private final KnowledgeBaseServiceImpl kbService;
    private final EmbedTaskPublisher embedTaskPublisher;

    @Value("${nexus.knowledge.upload-dir:/AstrBot/data/workspace/nexus-agent/data/uploads}")
    private String uploadDir;

    // ────────────────────────────────────────────────────────
    // Upload
    // ────────────────────────────────────────────────────────

    @Override
    @Transactional(rollbackFor = Exception.class)
    public DocumentVO upload(Long tenantId, Long userId, Long kbId, MultipartFile file) {
        // ① 权限校验（EDITOR 及以上）
        KnowledgeBase kb = kbService.requireKb(tenantId, kbId);
        kbService.checkPermission(tenantId, kbId, userId, "EDITOR");

        // ② 文件名安全校验（防路径穿越）
        String originalName = sanitizeFileName(file.getOriginalFilename());

        // ③ 文件类型白名单
        String ext = getExtension(originalName).toLowerCase();
        if (!ALLOWED_EXTENSIONS.contains(ext)) {
            throw new BizException(ResultCode.PARAM_ERROR,
                    "不支持的文件类型：" + ext + "，仅支持：" + String.join(", ", ALLOWED_EXTENSIONS));
        }

        // ④ 文件大小限制（50MB）
        if (file.getSize() > MAX_FILE_SIZE) {
            throw new BizException(ResultCode.PARAM_ERROR,
                    "文件超过 50MB 限制，实际大小：" + (file.getSize() / 1024 / 1024) + "MB");
        }

        // ⑤ 创建 document 记录（PENDING）
        Document doc = new Document();
        doc.setTenantId(tenantId);
        doc.setKbId(kbId);
        doc.setName(originalName);
        doc.setFileSize(file.getSize());
        doc.setFileType(ext);
        doc.setParseStatus("PENDING");
        doc.setChunkCount(0);
        doc.setCreateTime(LocalDateTime.now());
        doc.setUpdateTime(LocalDateTime.now());
        documentMapper.insert(doc);

        // ⑥ 保存文件到本地
        Path docDir = Paths.get(uploadDir, tenantId.toString(), doc.getId().toString());
        Path filePath = docDir.resolve(originalName);
        try {
            Files.createDirectories(docDir);
            file.transferTo(filePath.toFile());
        } catch (IOException e) {
            markFailed(doc.getId(), "文件保存失败：" + e.getMessage());
            throw new BizException(ResultCode.INTERNAL_ERROR, "文件保存失败");
        }

        // 更新 file_path
        documentMapper.update(null, new LambdaUpdateWrapper<Document>()
                .eq(Document::getId, doc.getId())
                .set(Document::getFilePath, filePath.toAbsolutePath().toString())
                .set(Document::getParseStatus, "PARSING")
                .set(Document::getUpdateTime, LocalDateTime.now()));
        doc.setFilePath(filePath.toAbsolutePath().toString());

        // ⑦ 提取文本并分片
        try {
            String text = extractText(filePath.toFile(), ext);
            List<String> chunks = chunkText(text, getChunkSize(kb), getChunkOverlap(kb));

            // 批量插入分片
            List<DocumentChunk> chunkEntities = new ArrayList<>();
            for (int i = 0; i < chunks.size(); i++) {
                DocumentChunk chunk = new DocumentChunk();
                chunk.setDocId(doc.getId());
                chunk.setKbId(kbId);
                chunk.setTenantId(tenantId);
                chunk.setChunkIndex(i);
                chunk.setContent(chunks.get(i));
                chunk.setCharCount(chunks.get(i).length());
                chunk.setCreateTime(LocalDateTime.now());
                chunkMapper.insert(chunk);
                chunkEntities.add(chunk);
            }

            // 更新 document 状态为 DONE
            documentMapper.update(null, new LambdaUpdateWrapper<Document>()
                    .eq(Document::getId, doc.getId())
                    .set(Document::getParseStatus, "DONE")
                    .set(Document::getChunkCount, chunks.size())
                    .set(Document::getUpdateTime, LocalDateTime.now()));
            doc.setParseStatus("DONE");
            doc.setChunkCount(chunks.size());

            // 更新知识库 doc_count +1
            kbMapper.update(null, new LambdaUpdateWrapper<KnowledgeBase>()
                    .eq(KnowledgeBase::getId, kbId)
                    .setSql("doc_count = doc_count + 1")
                    .set(KnowledgeBase::getUpdateTime, LocalDateTime.now()));

            log.info("Document[{}] uploaded: kbId={} chunks={}", doc.getId(), kbId, chunks.size());

            // 异步通知 embed-worker 向量化（失败不影响主流程）
            embedTaskPublisher.publishEmbedTask(
                    tenantId, kbId, doc.getId(), chunkEntities, safeName);

        } catch (Exception e) {
            markFailed(doc.getId(), e.getMessage());
            log.error("Document[{}] parse failed: {}", doc.getId(), e.getMessage(), e);
            doc.setParseStatus("FAILED");
            doc.setErrorMsg(e.getMessage());
        }

        return toVO(doc);
    }

    // ────────────────────────────────────────────────────────
    // List
    // ────────────────────────────────────────────────────────

    @Override
    public List<DocumentVO> list(Long tenantId, Long userId, Long kbId) {
        kbService.requireKb(tenantId, kbId);
        kbService.checkPermission(tenantId, kbId, userId, "VIEWER");

        return documentMapper.selectList(
                        new LambdaQueryWrapper<Document>()
                                .eq(Document::getTenantId, tenantId)
                                .eq(Document::getKbId, kbId)
                                .orderByDesc(Document::getCreateTime))
                .stream()
                .map(this::toVO)
                .collect(Collectors.toList());
    }

    // ────────────────────────────────────────────────────────
    // Delete
    // ────────────────────────────────────────────────────────

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(Long tenantId, Long userId, Long kbId, Long docId) {
        kbService.requireKb(tenantId, kbId);
        kbService.checkPermission(tenantId, kbId, userId, "EDITOR");

        Document doc = documentMapper.selectOne(
                new LambdaQueryWrapper<Document>()
                        .eq(Document::getId, docId)
                        .eq(Document::getTenantId, tenantId)
                        .eq(Document::getKbId, kbId));
        if (doc == null) {
            throw new BizException(ResultCode.NOT_FOUND, "文档不存在");
        }

        // 删除分片
        chunkMapper.delete(new LambdaQueryWrapper<DocumentChunk>()
                .eq(DocumentChunk::getDocId, docId));

        // 删除本地文件
        if (doc.getFilePath() != null) {
            deleteLocalFile(doc.getFilePath());
        }

        // 删除文档记录
        documentMapper.deleteById(docId);

        // 更新 doc_count
        kbMapper.update(null, new LambdaUpdateWrapper<KnowledgeBase>()
                .eq(KnowledgeBase::getId, kbId)
                .setSql("doc_count = GREATEST(doc_count - 1, 0)")
                .set(KnowledgeBase::getUpdateTime, LocalDateTime.now()));

        log.info("Document[{}] deleted from kb[{}]", docId, kbId);
    }

    // ────────────────────────────────────────────────────────
    // List Chunks
    // ────────────────────────────────────────────────────────

    @Override
    public List<DocumentChunk> listChunks(Long tenantId, Long userId, Long kbId, Long docId) {
        kbService.requireKb(tenantId, kbId);
        kbService.checkPermission(tenantId, kbId, userId, "VIEWER");

        return chunkMapper.selectList(
                new LambdaQueryWrapper<DocumentChunk>()
                        .eq(DocumentChunk::getDocId, docId)
                        .eq(DocumentChunk::getTenantId, tenantId)
                        .orderByAsc(DocumentChunk::getChunkIndex));
    }

    // ────────────────────────────────────────────────────────
    // Private Helpers
    // ────────────────────────────────────────────────────────

    /**
     * 提取文本内容。支持 txt/md/pdf；docx 返回提示信息（需额外依赖）。
     */
    private String extractText(File file, String ext) throws IOException {
        return switch (ext) {
            case "txt", "md" -> Files.readString(file.toPath(), StandardCharsets.UTF_8);
            case "pdf" -> extractPdfText(file);
            case "docx" -> "DOCX 解析暂不支持，请转换为 txt/pdf 格式";
            default -> throw new BizException(ResultCode.PARAM_ERROR, "不支持的文件类型：" + ext);
        };
    }

    private String extractPdfText(File file) throws IOException {
        try (PDDocument pdf = Loader.loadPDF(file)) {
            PDFTextStripper stripper = new PDFTextStripper();
            return stripper.getText(pdf);
        }
    }

    /**
     * 将文本按 chunkSize/chunkOverlap 切分。
     *
     * @param text         原文本
     * @param chunkSize    每片最大字符数
     * @param chunkOverlap 相邻分片的重叠字符数
     */
    public List<String> chunkText(String text, int chunkSize, int chunkOverlap) {
        if (text == null || text.isBlank()) {
            return List.of();
        }
        List<String> chunks = new ArrayList<>();
        int start = 0;
        int len = text.length();
        int step = Math.max(1, chunkSize - chunkOverlap);

        while (start < len) {
            int end = Math.min(start + chunkSize, len);
            chunks.add(text.substring(start, end));
            if (end == len) break;
            start += step;
        }
        return chunks;
    }

    private int getChunkSize(KnowledgeBase kb) {
        return parseChunkConfigInt(kb.getChunkConfig(), "chunkSize", 500);
    }

    private int getChunkOverlap(KnowledgeBase kb) {
        return parseChunkConfigInt(kb.getChunkConfig(), "chunkOverlap", 50);
    }

    /**
     * 使用 Jackson ObjectMapper 解析 chunkConfig JSON 中的整型字段。
     *
     * <p>chunkConfig 格式示例：{@code {"chunkSize":500,"chunkOverlap":50}}
     *
     * @param chunkConfig JSON 字符串
     * @param key         字段名
     * @param defaultVal  默认值
     * @return 解析结果，失败返回默认值
     */
    private int parseChunkConfigInt(String chunkConfig, String key, int defaultVal) {
        if (chunkConfig == null || chunkConfig.isBlank()) {
            return defaultVal;
        }
        try {
            com.fasterxml.jackson.databind.JsonNode root =
                    new com.fasterxml.jackson.databind.ObjectMapper().readTree(chunkConfig);
            com.fasterxml.jackson.databind.JsonNode node = root.get(key);
            if (node != null && node.isNumber()) {
                return node.asInt(defaultVal);
            }
            return defaultVal;
        } catch (Exception e) {
            log.warn("解析 chunkConfig 失败: key={}, config={}, error={}", key, chunkConfig, e.getMessage());
            return defaultVal;
        }
    }

    /**
     * 文件名安全校验：防路径穿越攻击。
     */
    private String sanitizeFileName(String name) {
        if (name == null || name.isBlank()) {
            throw new BizException(ResultCode.PARAM_ERROR, "文件名不能为空");
        }
        // 防止路径穿越
        if (name.contains("..") || name.contains("/") || name.contains("\\")) {
            throw new BizException(ResultCode.PARAM_ERROR, "非法文件名：" + name);
        }
        return name;
    }

    private String getExtension(String filename) {
        int dot = filename.lastIndexOf('.');
        if (dot < 0) return "";
        return filename.substring(dot + 1);
    }

    private void markFailed(Long docId, String errorMsg) {
        documentMapper.update(null, new LambdaUpdateWrapper<Document>()
                .eq(Document::getId, docId)
                .set(Document::getParseStatus, "FAILED")
                .set(Document::getErrorMsg, errorMsg)
                .set(Document::getUpdateTime, LocalDateTime.now()));
    }

    private void deleteLocalFile(String filePath) {
        try {
            Path path = Paths.get(filePath);
            Files.deleteIfExists(path);
            // 尝试删除父目录（如果为空）
            Path parent = path.getParent();
            if (parent != null && Files.exists(parent)) {
                File[] files = parent.toFile().listFiles();
                if (files != null && files.length == 0) {
                    Files.delete(parent);
                }
            }
        } catch (IOException e) {
            log.warn("Failed to delete file: {}", filePath, e);
        }
    }

    private DocumentVO toVO(Document doc) {
        return DocumentVO.builder()
                .id(doc.getId())
                .tenantId(doc.getTenantId())
                .kbId(doc.getKbId())
                .name(doc.getName())
                .fileSize(doc.getFileSize())
                .fileType(doc.getFileType())
                .parseStatus(doc.getParseStatus())
                .chunkCount(doc.getChunkCount())
                .errorMsg(doc.getErrorMsg())
                .createTime(doc.getCreateTime())
                .updateTime(doc.getUpdateTime())
                .build();
    }
}
