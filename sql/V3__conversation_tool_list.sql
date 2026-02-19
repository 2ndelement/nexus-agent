-- ============================================================================
-- V3: 会话工具列表 + 权限检查优化
-- ============================================================================

-- 1. 更新 conversation 表添加 tool_list 字段
ALTER TABLE conversation
ADD COLUMN tool_list JSON COMMENT '会话开始时的可用工具列表';

-- 2. 新增 ToolPermission 表（如果不存在）
CREATE TABLE IF NOT EXISTS `tool_permission` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `role_id` BIGINT NOT NULL COMMENT '角色ID',
    `tool_name` VARCHAR(100) NOT NULL COMMENT '工具名称',
    `tool_source` ENUM('BUILTIN', 'MCP', 'CUSTOM') NOT NULL COMMENT '工具来源',
    `permission` TINYINT NOT NULL DEFAULT 1 COMMENT '1=允许 0=禁止',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_role_tool` (`tenant_id`, `role_id`, `tool_name`, `tool_source`),
    INDEX `idx_role` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色工具权限表';

-- 3. 新增审计日志表（如果不存在）
CREATE TABLE IF NOT EXISTS `audit_log` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `tenant_id` BIGINT COMMENT '租户ID',
    `user_id` BIGINT COMMENT '用户ID',
    `action_type` VARCHAR(50) NOT NULL COMMENT '操作类型',
    `resource_type` VARCHAR(50) NOT NULL COMMENT '资源类型',
    `resource_id` VARCHAR(100) COMMENT '资源ID',
    `detail` JSON COMMENT '操作详情',
    `ip_address` VARCHAR(50) COMMENT 'IP地址',
    `user_agent` VARCHAR(500) COMMENT 'User-Agent',
    `result` TINYINT DEFAULT 1 COMMENT '1=成功 0=失败',
    `error_message` TEXT COMMENT '错误信息',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_tenant_time` (`tenant_id`, `created_at`),
    INDEX `idx_user_time` (`user_id`, `created_at`),
    INDEX `idx_action` (`action_type`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='审计日志表';

-- 4. 初始化默认内置工具权限（所有角色默认允许内置工具）
-- 注意：这需要根据实际角色ID来插入
