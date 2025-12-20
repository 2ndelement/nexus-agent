-- MySQL 生产环境建表脚本
CREATE TABLE IF NOT EXISTS `knowledge_base` (
  `id`           BIGINT AUTO_INCREMENT PRIMARY KEY,
  `tenant_id`    BIGINT NOT NULL,
  `name`         VARCHAR(100) NOT NULL COMMENT '知识库名称',
  `description`  TEXT,
  `type`         VARCHAR(20) DEFAULT 'GENERAL' COMMENT 'GENERAL/QA/CODE',
  `embed_model`  VARCHAR(100) DEFAULT 'sentence-transformers' COMMENT '使用的 Embedding 模型',
  `chunk_config` TEXT COMMENT '分片策略 JSON',
  `status`       TINYINT DEFAULT 1 COMMENT '1=正常 2=构建中 0=禁用',
  `doc_count`    INT DEFAULT 0,
  `create_time`  DATETIME DEFAULT CURRENT_TIMESTAMP,
  `update_time`  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_tenant_name` (`tenant_id`, `name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `document` (
  `id`           BIGINT AUTO_INCREMENT PRIMARY KEY,
  `tenant_id`    BIGINT NOT NULL,
  `kb_id`        BIGINT NOT NULL COMMENT '所属知识库',
  `name`         VARCHAR(255) NOT NULL COMMENT '文件名',
  `file_path`    VARCHAR(500) COMMENT '本地/OSS路径',
  `file_size`    BIGINT COMMENT '文件大小(bytes)',
  `file_type`    VARCHAR(20) COMMENT 'pdf/txt/md/docx',
  `parse_status` VARCHAR(20) DEFAULT 'PENDING' COMMENT 'PENDING/PARSING/DONE/FAILED',
  `chunk_count`  INT DEFAULT 0 COMMENT '切片数量',
  `error_msg`    TEXT,
  `create_time`  DATETIME DEFAULT CURRENT_TIMESTAMP,
  `update_time`  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY `idx_kb` (`kb_id`, `tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `kb_permission` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `tenant_id`   BIGINT NOT NULL,
  `kb_id`       BIGINT NOT NULL,
  `user_id`     BIGINT NOT NULL,
  `role`        VARCHAR(20) NOT NULL COMMENT 'OWNER/EDITOR/VIEWER',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_kb_user` (`kb_id`, `user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `kb_agent_binding` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `tenant_id`   BIGINT NOT NULL,
  `kb_id`       BIGINT NOT NULL,
  `agent_id`    BIGINT NOT NULL,
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_kb_agent` (`kb_id`, `agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
