-- ============================================================================
-- NexusAgent V6: 多平台机器人支持
--
-- 变更说明：
-- 1. 新增 bot 表 - 机器人配置（一个 Agent 可绑定多个 Bot）
-- 2. 新增 bot_binding 表 - 用户-平台-机器人绑定
-- 3. 修改 conversation 表 - 添加 platform 和 bot_id 字段
-- ============================================================================

-- ============================================================================
-- 1. 创建 Bot 表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `bot` (
    `id`              BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `bot_name`        VARCHAR(100) NOT NULL COMMENT 'Bot名称',
    `platform`        ENUM('QQ', 'QQ_GUILD', 'FEISHU', 'WECHAT', 'TELEGRAM', 'WEB') NOT NULL DEFAULT 'WEB' COMMENT '平台类型',
    `app_id`          VARCHAR(100) COMMENT '平台AppID',
    `app_secret`      VARCHAR(255) COMMENT '平台AppSecret',
    `bot_token`       VARCHAR(500) COMMENT 'Bot Token',
    `agent_id`        BIGINT COMMENT '绑定的Agent配置ID',
    `owner_type`      ENUM('PERSONAL', 'ORGANIZATION') NOT NULL DEFAULT 'PERSONAL' COMMENT '归属类型',
    `owner_id`        BIGINT NOT NULL DEFAULT 0 COMMENT '归属ID（用户ID或组织ID）',
    `status`          TINYINT DEFAULT 1 COMMENT '1=启用 0=禁用',
    `config`          JSON COMMENT '平台特定配置',
    `created_at`      DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at`      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_agent` (`agent_id`),
    INDEX `idx_owner` (`owner_type`, `owner_id`),
    UNIQUE KEY `uk_platform_app` (`platform`, `app_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Bot表';

-- ============================================================================
-- 2. 创建 BotBinding 表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `bot_binding` (
    `id`              BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `bot_id`          BIGINT NOT NULL COMMENT 'Bot ID',
    `user_id`         BIGINT NOT NULL COMMENT 'Nexus用户ID',
    `puid`            VARCHAR(100) NOT NULL COMMENT '平台用户ID',
    `extra_data`      JSON COMMENT '平台特定数据（昵称、头像等）',
    `status`          TINYINT DEFAULT 1 COMMENT '1=正常 0=已解绑',
    `created_at`      DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at`      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_bot_puid` (`bot_id`, `puid`),
    INDEX `idx_user` (`user_id`),
    CONSTRAINT `fk_binding_bot` FOREIGN KEY (`bot_id`) REFERENCES `bot`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Bot绑定表';

-- ============================================================================
-- 3. 修改 conversation 表
-- ============================================================================
ALTER TABLE `conversation`
    ADD COLUMN `platform` VARCHAR(20) DEFAULT 'WEB' COMMENT '平台来源' AFTER `owner_id`,
    ADD COLUMN `bot_id` BIGINT COMMENT 'Bot ID' AFTER `platform`,
    ADD INDEX `idx_platform_bot` (`platform`, `bot_id`);

-- ============================================================================
-- 4. 创建默认 Web Bot（用于前端）
-- ============================================================================
-- Web Bot 作为前端聊天的默认 Bot
INSERT INTO `bot` (`id`, `bot_name`, `platform`, `agent_id`, `owner_type`, `owner_id`, `status`) VALUES
(1, 'WebChat', 'WEB', 1, 'PERSONAL', 1, 1)
ON DUPLICATE KEY UPDATE `bot_name` = VALUES(`bot_name`);

-- ============================================================================
-- 完成提示
-- ============================================================================
SELECT 'V6 bot_platform completed' AS status;
