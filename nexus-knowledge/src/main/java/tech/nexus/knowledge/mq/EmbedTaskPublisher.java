package tech.nexus.knowledge.mq;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.stereotype.Component;
import tech.nexus.knowledge.entity.DocumentChunk;

import java.util.*;

/**
 * 向 embed-worker 发布向量化任务消息。
 *
 * <p>消息格式与 embed-worker 的 EmbedTask schema 对齐：
 * <pre>{@code
 * {
 *   "task_id":   "uuid",
 *   "tenant_id": "1",
 *   "kb_id":     "101",
 *   "doc_id":    "9001",
 *   "chunks": [
 *     {"chunk_id": "...", "chunk_index": 0, "content": "...", "metadata": {...}}
 *   ]
 * }
 * }</pre>
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class EmbedTaskPublisher {

    private final RabbitTemplate rabbitTemplate;
    private final ObjectMapper objectMapper;

    @Value("${nexus.knowledge.embed-queue:nexus.embed.tasks}")
    private String embedQueue;

    /**
     * 声明队列（幂等，首次启动时自动创建）。
     */
    @Bean
    public Queue embedTaskQueue() {
        return new Queue(embedQueue, true); // durable
    }

    /**
     * 发布向量化任务。
     *
     * @param tenantId 租户ID
     * @param kbId     知识库ID
     * @param docId    文档ID
     * @param chunks   分片列表
     * @param fileName 原始文件名（写入 metadata）
     */
    public void publishEmbedTask(
            Long tenantId,
            Long kbId,
            Long docId,
            List<DocumentChunk> chunks,
            String fileName
    ) {
        try {
            String taskId = UUID.randomUUID().toString();

            List<Map<String, Object>> chunkPayloads = new ArrayList<>();
            for (DocumentChunk chunk : chunks) {
                Map<String, Object> payload = new LinkedHashMap<>();
                payload.put("chunk_id", String.valueOf(chunk.getId()));
                payload.put("chunk_index", chunk.getChunkIndex());
                payload.put("content", chunk.getContent());

                Map<String, Object> meta = new LinkedHashMap<>();
                meta.put("doc_id", String.valueOf(docId));
                meta.put("filename", fileName);
                meta.put("chunk_index", chunk.getChunkIndex());
                payload.put("metadata", meta);

                chunkPayloads.add(payload);
            }

            Map<String, Object> message = new LinkedHashMap<>();
            message.put("task_id", taskId);
            message.put("tenant_id", String.valueOf(tenantId));
            message.put("kb_id", String.valueOf(kbId));
            message.put("doc_id", String.valueOf(docId));
            message.put("chunks", chunkPayloads);

            String json = objectMapper.writeValueAsString(message);
            rabbitTemplate.convertAndSend(embedQueue, json);

            log.info("[Embed] 已发布向量化任务: taskId={}, docId={}, chunks={}",
                    taskId, docId, chunks.size());

        } catch (Exception e) {
            log.error("[Embed] 发布向量化任务失败: docId={}, error={}", docId, e.getMessage(), e);
            // 不抛异常，不影响文档上传主流程（向量化可重试）
        }
    }
}
