-- H2 兼容 DDL（测试用）

CREATE TABLE IF NOT EXISTS `agent_config` (
  `id`            BIGINT AUTO_INCREMENT PRIMARY KEY,
  `tenant_id`     BIGINT NOT NULL,
  `name`          VARCHAR(100) NOT NULL,
  `description`   TEXT,
  `avatar`        VARCHAR(500),
  `system_prompt` CLOB,
  `model`         VARCHAR(100) DEFAULT 'MiniMax-M2.5-highspeed',
  `temperature`   DECIMAL(3,2) DEFAULT 0.70,
  `max_tokens`    INT DEFAULT 2000,
  `tools`         VARCHAR(2000),
  `kb_ids`        VARCHAR(2000),
  `version`       INT DEFAULT 1,
  `status`        TINYINT DEFAULT 1,
  `is_public`     TINYINT DEFAULT 0,
  `create_time`   DATETIME DEFAULT CURRENT_TIMESTAMP,
  `update_time`   DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `uk_tenant_name` UNIQUE (`tenant_id`, `name`)
);

CREATE TABLE IF NOT EXISTS `agent_config_history` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `agent_id`    BIGINT NOT NULL,
  `tenant_id`   BIGINT NOT NULL,
  `version`     INT NOT NULL,
  `snapshot`    CLOB NOT NULL,
  `change_note` VARCHAR(500),
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `tool_registry` (
  `id`           BIGINT AUTO_INCREMENT PRIMARY KEY,
  `name`         VARCHAR(100) NOT NULL,
  `display_name` VARCHAR(100),
  `description`  TEXT,
  `schema`       CLOB,
  `endpoint`     VARCHAR(500),
  `is_builtin`   TINYINT DEFAULT 1,
  `create_time`  DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `uk_tool_name` UNIQUE (`name`)
);

CREATE TABLE IF NOT EXISTS `skill` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `name`        VARCHAR(100) NOT NULL,
  `description` TEXT NOT NULL,
  `file_path`   VARCHAR(500) NOT NULL COMMENT '本地存储路径 /tmp/nexus-skills/{name}/SKILL.md',
  `content`     CLOB COMMENT 'SKILL.md 完整内容（冗余存储，便于全文检索）',
  `keywords`    VARCHAR(1000) COMMENT 'RAG关键词，逗号分隔',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `uk_skill_name` UNIQUE (`name`)
);

CREATE TABLE IF NOT EXISTS `agent_skill` (
  `id`         BIGINT AUTO_INCREMENT PRIMARY KEY,
  `agent_id`   BIGINT NOT NULL,
  `skill_name` VARCHAR(100) NOT NULL,
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `uk_agent_skill` UNIQUE (`agent_id`, `skill_name`)
);
