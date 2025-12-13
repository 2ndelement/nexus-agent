-- 生产环境建表脚本（MySQL）
CREATE TABLE IF NOT EXISTS `conversation` (
  `id`            VARCHAR(64) NOT NULL COMMENT '会话ID (UUID)',
  `tenant_id`     BIGINT NOT NULL COMMENT '租户ID',
  `user_id`       BIGINT NOT NULL COMMENT '用户ID',
  `title`         VARCHAR(200) DEFAULT '新对话' COMMENT '对话标题',
  `agent_id`      BIGINT COMMENT '使用的 Agent 配置ID',
  `model`         VARCHAR(100) DEFAULT 'MiniMax-M2.5-highspeed' COMMENT '使用的模型',
  `status`        TINYINT DEFAULT 1 COMMENT '1=活跃 0=已归档',
  `message_count` INT DEFAULT 0,
  `create_time`   DATETIME DEFAULT CURRENT_TIMESTAMP,
  `update_time`   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_tenant_user` (`tenant_id`, `user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `message` (
  `id`              BIGINT AUTO_INCREMENT PRIMARY KEY,
  `conversation_id` VARCHAR(64) NOT NULL,
  `tenant_id`       BIGINT NOT NULL COMMENT '冗余字段，便于隔离查询',
  `role`            VARCHAR(20) NOT NULL COMMENT 'user/assistant/system/tool',
  `content`         LONGTEXT NOT NULL,
  `tokens`          INT DEFAULT 0 COMMENT 'token 消耗数',
  `metadata`        TEXT COMMENT '工具调用结果、引用来源等',
  `idempotent_key`  VARCHAR(128) COMMENT '幂等Key',
  `create_time`     DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY `idx_conv_time` (`conversation_id`, `create_time`),
  UNIQUE KEY `uk_tenant_conv_idem` (`tenant_id`, `conversation_id`, `idempotent_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
