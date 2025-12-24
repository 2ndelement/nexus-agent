package tech.nexus.knowledge.service;

import org.springframework.web.multipart.MultipartFile;
import tech.nexus.knowledge.dto.DocumentVO;
import tech.nexus.knowledge.entity.DocumentChunk;

import java.util.List;

/**
 * 文档管理服务接口。
 *
 * <p>处理文档上传、文本提取、分片存储等操作。
 */
public interface DocumentService {

    /**
     * 上传文档（支持 txt/md/pdf）：
     * <ol>
     *   <li>文件类型白名单校验（pdf/txt/md/docx）</li>
     *   <li>文件大小限制（≤50MB）</li>
     *   <li>保存文件到本地</li>
     *   <li>创建 document 记录（PENDING）</li>
     *   <li>同步提取文本 → 分片 → 存储 document_chunk</li>
     *   <li>更新 document 状态为 DONE（失败则 FAILED + error_msg）</li>
     * </ol>
     *
     * @param tenantId 租户 ID
     * @param userId   操作用户 ID（需要 EDITOR 及以上权限）
     * @param kbId     知识库 ID
     * @param file     上传文件
     * @return 文档 VO
     */
    DocumentVO upload(Long tenantId, Long userId, Long kbId, MultipartFile file);

    /**
     * 列出知识库下的所有文档。
     *
     * @param tenantId 租户 ID（需要 VIEWER 权限）
     * @param userId   操作用户 ID
     * @param kbId     知识库 ID
     */
    List<DocumentVO> list(Long tenantId, Long userId, Long kbId);

    /**
     * 删除文档（需要 EDITOR 及以上权限）：
     * <ol>
     *   <li>删除 document_chunk 记录</li>
     *   <li>删除本地文件</li>
     *   <li>删除 document 记录</li>
     *   <li>更新 knowledge_base.doc_count</li>
     * </ol>
     */
    void delete(Long tenantId, Long userId, Long kbId, Long docId);

    /**
     * 查询文档的分片列表（需要 VIEWER 权限）。
     */
    List<DocumentChunk> listChunks(Long tenantId, Long userId, Long kbId, Long docId);
}
