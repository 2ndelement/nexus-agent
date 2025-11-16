# CLAUDE.md — nexus-knowledge

> 本文件由帕托莉维护，Claude Code 必须在开始前完整阅读。

---

## 服务职责

`nexus-knowledge` 是知识库管理服务（Java 层），负责：
1. 知识库（KnowledgeBase）的 CRUD 管理
2. 文档上传任务调度（调用 rag-service Python 进行向量化）
3. 文档元数据管理（存 MySQL）
4. 知识库与 Agent 的绑定关系管理
5. 文档解析任务状态追踪

**不负责：** 实际向量化与检索（由 Python rag-service 负责）

---

## 技术约束

| 约束 | 说明 |
|------|------|
| **框架** | Spring Boot 3.x, MyBatis-Plus |
| **依赖** | nexus-common |
| **数据库** | MySQL 127.0.0.1:3306/nexus_agent |
| **调用下游** | HTTP 调用 rag-service (127.0.0.1:8005) |
| **文件存储** | 容器内：本地文件系统 /data/uploads/{tenantId}/；生产：MinIO |
| **端口** | 8006 |

---

## 数据模型

```sql
CREATE TABLE `knowledge_base` (
  `id`           BIGINT AUTO_INCREMENT PRIMARY KEY,
  `tenant_id`    BIGINT NOT NULL,
  `name`         VARCHAR(100) NOT NULL COMMENT '知识库名称',
  `description`  TEXT,
  `embed_model`  VARCHAR(100) DEFAULT 'sentence-transformers' COMMENT '使用的 Embedding 模型',
  `status`       TINYINT DEFAULT 1 COMMENT '1=正常 2=构建中 0=禁用',
  `doc_count`    INT DEFAULT 0,
  `create_time`  DATETIME DEFAULT CURRENT_TIMESTAMP,
  `update_time`  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_tenant_name` (`tenant_id`, `name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `document` (
  `id`               BIGINT AUTO_INCREMENT PRIMARY KEY,
  `tenant_id`        BIGINT NOT NULL,
  `kb_id`            BIGINT NOT NULL COMMENT '所属知识库',
  `name`             VARCHAR(255) NOT NULL COMMENT '文件名',
  `file_path`        VARCHAR(500) COMMENT '本地/OSS路径',
  `file_size`        BIGINT COMMENT '文件大小(bytes)',
  `file_type`        VARCHAR(20) COMMENT 'pdf/txt/md/docx',
  `parse_status`     VARCHAR(20) DEFAULT 'PENDING' COMMENT 'PENDING/PARSING/DONE/FAILED',
  `chunk_count`      INT DEFAULT 0 COMMENT '切片数量',
  `error_msg`        TEXT,
  `create_time`      DATETIME DEFAULT CURRENT_TIMESTAMP,
  `update_time`      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY `idx_kb` (`kb_id`, `tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `kb_agent_binding` (
  `id`         BIGINT AUTO_INCREMENT PRIMARY KEY,
  `tenant_id`  BIGINT NOT NULL,
  `kb_id`      BIGINT NOT NULL,
  `agent_id`   BIGINT NOT NULL,
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_kb_agent` (`kb_id`, `agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 当前任务

### Task-08: 实现 nexus-knowledge 知识库管理服务

**API 接口：**

```
POST   /api/knowledge/bases                      创建知识库
GET    /api/knowledge/bases                      列出知识库（分页）
DELETE /api/knowledge/bases/{id}                 删除知识库

POST   /api/knowledge/bases/{kbId}/documents     上传文档（multipart/form-data）
GET    /api/knowledge/bases/{kbId}/documents     文档列表
DELETE /api/knowledge/bases/{kbId}/documents/{docId}  删除文档

POST   /api/knowledge/bases/{kbId}/bind/{agentId}    绑定到 Agent
DELETE /api/knowledge/bases/{kbId}/bind/{agentId}    解绑
```

**文档上传流程：**
```
1. 接收文件 → 保存到本地 /data/uploads/{tenantId}/{docId}/
2. 创建 document 记录（status=PENDING）
3. 异步 HTTP POST 到 rag-service /api/v1/knowledge/ingest
   body: { doc_id, file_path, tenant_id, kb_id }
4. rag-service 完成后回调更新 status=DONE
```

---

## 测试要求

- [ ] 创建知识库 → 返回 ID
- [ ] 租户A的知识库不能被租户B查询
- [ ] 上传文档 → status=PENDING → 异步调用 rag-service（Mock测试）
- [ ] 知识库绑定 Agent → 幂等处理

---

## Code Review 检查清单

- [ ] 文件上传限制大小（50MB）
- [ ] 文件类型白名单校验（pdf/txt/md/docx）
- [ ] 调用 rag-service 失败时 document.status 更新为 FAILED + error_msg
- [ ] 本地文件路径不允许路径穿越攻击（../ 过滤）
- [ ] 所有 DB 查询带 tenant_id WHERE 条件

---

## 注意事项

1. 容器内文件存储用 `/AstrBot/data/workspace/nexus-agent/data/uploads/` 目录
2. rag-service 调用用 RestTemplate/WebClient，测试时 Mock
3. 先设计接口 + DB，等帕托莉确认再实现
