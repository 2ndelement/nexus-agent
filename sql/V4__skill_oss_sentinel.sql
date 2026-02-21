-- ============================================================================
-- Skill 存储 + OSS 挂载 + Sentinel 租户限流
-- ============================================================================

-- ============================================================================
-- 1. Skill 存储配置表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `skill_config` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `bucket` VARCHAR(200) NOT NULL COMMENT 'OSS Bucket 名',
    `endpoint` VARCHAR(200) NOT NULL COMMENT 'OSS Endpoint',
    `access_key` VARCHAR(100) NOT NULL COMMENT 'AccessKey',
    `secret_key` VARCHAR(200) NOT NULL COMMENT 'SecretKey',
    `region` VARCHAR(50) DEFAULT 'cn-hangzhou' COMMENT 'OSS Region',
    `skills_path` VARCHAR(200) DEFAULT 'skills' COMMENT 'Skills 目录',
    `status` TINYINT DEFAULT 1 COMMENT '1=启用',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_tenant` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='租户 Skill OSS 存储配置';

-- ============================================================================
-- 2. Agent-Skill 绑定表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `agent_skill_binding` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `agent_id` BIGINT NOT NULL COMMENT 'Agent ID',
    `skill_name` VARCHAR(100) NOT NULL COMMENT 'Skill 目录名',
    `skill_path` VARCHAR(200) COMMENT 'Skill 子目录（可选，覆盖默认',
    `enabled` BOOLEAN DEFAULT TRUE,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_agent_skill` (`agent_id`, `skill_name`),
    INDEX `idx_agent` (`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent-Skill 绑定';

-- ============================================================================
-- 3. Sentinel 租户限流配置表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `tenant_flow_config` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `api_path` VARCHAR(100) NOT NULL COMMENT 'API 路径',
    `qps` INT DEFAULT 50 COMMENT 'QPS 限流阈值',
    `enabled` BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_tenant_api` (`tenant_id`, `api_path`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='租户限流配置';
