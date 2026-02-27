-- ============================================================================
-- NexusAgent V5: 用户与组织系统重构
--
-- 变更说明：
-- 1. 用户不再绑定租户，可独立注册
-- 2. 新增组织表 (organization) 替代租户概念
-- 3. 新增组织成员表 (organization_user)
-- 4. 新增组织邀请表 (organization_invite)
-- 5. Agent 支持个人/组织两种归属类型
-- ============================================================================

-- ============================================================================
-- 1. 创建组织表 (替代 tenant 表)
-- ============================================================================
CREATE TABLE IF NOT EXISTS `organization` (
    `id`              BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `code`            VARCHAR(50) NOT NULL COMMENT '组织代码（URL友好，全局唯一）',
    `name`            VARCHAR(100) NOT NULL COMMENT '组织名称',
    `description`     VARCHAR(500) COMMENT '组织描述',
    `avatar`          VARCHAR(500) COMMENT '组织头像URL',
    `owner_id`        BIGINT NOT NULL COMMENT '创建者ID（OWNER）',
    `plan`            VARCHAR(20) DEFAULT 'FREE' COMMENT '套餐：FREE/PRO/ENTERPRISE',
    `status`          TINYINT DEFAULT 1 COMMENT '1=正常 0=禁用',
    `member_limit`    INT DEFAULT 5 COMMENT '成员数量上限',
    `agent_limit`     INT DEFAULT 10 COMMENT 'Agent数量上限',
    `created_at`      DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at`      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_code` (`code`),
    INDEX `idx_owner` (`owner_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='组织表';

-- ============================================================================
-- 2. 创建组织成员表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `organization_user` (
    `id`              BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `organization_id` BIGINT NOT NULL COMMENT '组织ID',
    `user_id`         BIGINT NOT NULL COMMENT '用户ID',
    `role`            VARCHAR(20) DEFAULT 'MEMBER' COMMENT 'OWNER/ADMIN/MEMBER',
    `status`          TINYINT DEFAULT 1 COMMENT '1=正常 0=已离开',
    `joined_at`       DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '加入时间',
    `invited_by`      BIGINT COMMENT '邀请人ID',
    UNIQUE KEY `uk_org_user` (`organization_id`, `user_id`),
    INDEX `idx_user` (`user_id`),
    INDEX `idx_org` (`organization_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='组织成员表';

-- ============================================================================
-- 3. 创建组织邀请表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `organization_invite` (
    `id`              BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `organization_id` BIGINT NOT NULL COMMENT '组织ID',
    `email`           VARCHAR(100) COMMENT '邀请邮箱（可选）',
    `invite_code`     VARCHAR(50) NOT NULL COMMENT '邀请码',
    `role`            VARCHAR(20) DEFAULT 'MEMBER' COMMENT '邀请角色：ADMIN/MEMBER',
    `invited_by`      BIGINT NOT NULL COMMENT '邀请人ID',
    `status`          TINYINT DEFAULT 0 COMMENT '0=待接受 1=已接受 2=已过期 3=已取消',
    `expire_at`       DATETIME NOT NULL COMMENT '过期时间',
    `accepted_at`     DATETIME COMMENT '接受时间',
    `accepted_by`     BIGINT COMMENT '接受人ID',
    `created_at`      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_code` (`invite_code`),
    INDEX `idx_org` (`organization_id`),
    INDEX `idx_expire` (`expire_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='组织邀请表';

-- ============================================================================
-- 4. 修改用户表：移除 tenant_id 绑定，添加配额字段
-- ============================================================================

-- 4.1 添加新字段（先添加，再处理约束）
ALTER TABLE `user`
    ADD COLUMN `personal_agent_limit` INT DEFAULT 1 COMMENT '个人Agent数量上限' AFTER `status`,
    ADD COLUMN `org_create_limit` INT DEFAULT 3 COMMENT '可创建组织数量上限' AFTER `personal_agent_limit`,
    ADD COLUMN `org_join_limit` INT DEFAULT 10 COMMENT '可加入组织数量上限' AFTER `org_create_limit`;

-- 4.2 删除旧的唯一约束（tenant_id + username）
ALTER TABLE `user` DROP INDEX `uk_tenant_username`;

-- 4.3 添加新的唯一约束（username 全局唯一）
ALTER TABLE `user` ADD UNIQUE INDEX `uk_username` (`username`);

-- 4.4 添加 email 唯一约束（如果有值）
ALTER TABLE `user` ADD UNIQUE INDEX `uk_email` (`email`);

-- 4.5 将 tenant_id 设为可空（保留用于数据迁移，后续可删除）
ALTER TABLE `user` MODIFY COLUMN `tenant_id` BIGINT NULL COMMENT '旧租户ID（已废弃）';

-- ============================================================================
-- 5. 修改 Agent 配置表：支持 PERSONAL / ORGANIZATION 归属
-- ============================================================================
ALTER TABLE `agent_config`
    ADD COLUMN `owner_type` ENUM('PERSONAL', 'ORGANIZATION') NOT NULL DEFAULT 'ORGANIZATION'
        COMMENT '归属类型' AFTER `id`,
    ADD COLUMN `owner_id` BIGINT NOT NULL DEFAULT 0
        COMMENT '归属ID（用户ID或组织ID）' AFTER `owner_type`,
    ADD COLUMN `max_context` INT DEFAULT 128000
        COMMENT '最大上下文token数（默认128k）' AFTER `max_tokens`,
    ADD INDEX `idx_owner` (`owner_type`, `owner_id`);

-- ============================================================================
-- 6. 修改会话表：支持 PERSONAL / ORGANIZATION 归属
-- ============================================================================
ALTER TABLE `conversation`
    ADD COLUMN `owner_type` ENUM('PERSONAL', 'ORGANIZATION') NOT NULL DEFAULT 'ORGANIZATION'
        COMMENT '归属类型' AFTER `conversation_id`,
    ADD COLUMN `owner_id` BIGINT NOT NULL DEFAULT 0
        COMMENT '归属ID（用户ID或组织ID）' AFTER `owner_type`,
    ADD INDEX `idx_owner` (`owner_type`, `owner_id`);

-- ============================================================================
-- 7. 数据迁移：将旧数据迁移到新结构
-- ============================================================================

-- 7.1 为每个租户创建对应的组织
INSERT INTO `organization` (`id`, `code`, `name`, `owner_id`, `status`, `created_at`)
SELECT
    t.`id`,
    t.`code`,
    t.`name`,
    COALESCE((SELECT MIN(u.`id`) FROM `user` u WHERE u.`tenant_id` = t.`id`), 1),
    t.`status`,
    t.`created_at`
FROM `tenant` t
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`);

-- 7.2 将租户下的用户添加为组织成员
INSERT INTO `organization_user` (`organization_id`, `user_id`, `role`, `status`, `joined_at`)
SELECT
    u.`tenant_id`,
    u.`id`,
    CASE
        WHEN u.`id` = (SELECT MIN(u2.`id`) FROM `user` u2 WHERE u2.`tenant_id` = u.`tenant_id`)
        THEN 'OWNER'
        ELSE 'MEMBER'
    END,
    1,
    u.`created_at`
FROM `user` u
WHERE u.`tenant_id` IS NOT NULL
ON DUPLICATE KEY UPDATE `role` = VALUES(`role`);

-- 7.3 迁移 Agent 归属信息
UPDATE `agent_config` SET
    `owner_type` = 'ORGANIZATION',
    `owner_id` = `tenant_id`
WHERE `tenant_id` IS NOT NULL AND `tenant_id` > 0;

-- 7.4 迁移会话归属信息
UPDATE `conversation` SET
    `owner_type` = 'ORGANIZATION',
    `owner_id` = `tenant_id`
WHERE `tenant_id` IS NOT NULL AND `tenant_id` > 0;

-- ============================================================================
-- 8. 修改知识库表：支持 PERSONAL / ORGANIZATION 归属
-- ============================================================================
ALTER TABLE `knowledge_base`
    ADD COLUMN `owner_type` ENUM('PERSONAL', 'ORGANIZATION') NOT NULL DEFAULT 'ORGANIZATION'
        COMMENT '归属类型' AFTER `id`,
    ADD COLUMN `owner_id` BIGINT NOT NULL DEFAULT 0
        COMMENT '归属ID' AFTER `owner_type`,
    ADD INDEX `idx_kb_owner` (`owner_type`, `owner_id`);

-- 迁移知识库归属
UPDATE `knowledge_base` SET
    `owner_type` = 'ORGANIZATION',
    `owner_id` = `tenant_id`
WHERE `tenant_id` IS NOT NULL AND `tenant_id` > 0;

-- ============================================================================
-- 9. 更新相关表的租户字段为可空
-- ============================================================================
ALTER TABLE `role` MODIFY COLUMN `tenant_id` BIGINT NULL COMMENT '旧租户ID（已废弃）';
ALTER TABLE `agent_config` MODIFY COLUMN `tenant_id` BIGINT NULL COMMENT '旧租户ID（已废弃）';
ALTER TABLE `conversation` MODIFY COLUMN `tenant_id` BIGINT NULL COMMENT '旧租户ID（已废弃）';
ALTER TABLE `knowledge_base` MODIFY COLUMN `tenant_id` BIGINT NULL COMMENT '旧租户ID（已废弃）';
ALTER TABLE `knowledge_doc` MODIFY COLUMN `tenant_id` BIGINT NULL COMMENT '旧租户ID（已废弃）';
ALTER TABLE `billing_record` MODIFY COLUMN `tenant_id` BIGINT NULL COMMENT '旧租户ID（已废弃）';

-- ============================================================================
-- 10. 创建刷新令牌表（用于 JWT 刷新）
-- ============================================================================
CREATE TABLE IF NOT EXISTS `refresh_token` (
    `id`              BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `user_id`         BIGINT NOT NULL COMMENT '用户ID',
    `token`           VARCHAR(500) NOT NULL COMMENT '刷新令牌',
    `device_info`     VARCHAR(200) COMMENT '设备信息',
    `ip_address`      VARCHAR(50) COMMENT 'IP地址',
    `expires_at`      DATETIME NOT NULL COMMENT '过期时间',
    `created_at`      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_token` (`token`(255)),
    INDEX `idx_user` (`user_id`),
    INDEX `idx_expires` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='刷新令牌表';

-- ============================================================================
-- 完成提示
-- ============================================================================
SELECT 'V5 user_org_refactor completed' AS status;
