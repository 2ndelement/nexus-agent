-- ============================================================================
-- NexusAgent 数据库变更
-- 版本: v2.0
-- 更新: MCP Server、工具权限、审计日志
-- ============================================================================

-- ============================================================================
-- 1. MCP Server 表
-- 存储用户配置的外部 MCP Server（支持 SSE / Streamable HTTP）
-- ============================================================================
CREATE TABLE IF NOT EXISTS `mcp_server` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `name` VARCHAR(100) NOT NULL COMMENT '服务器名称',
    `description` VARCHAR(500) DEFAULT NULL COMMENT '描述',
    -- MCP 配置（ModelScope 格式）
    `config_type` ENUM('sse', 'streamable_http') DEFAULT 'sse' COMMENT '传输类型',
    `config` JSON NOT NULL COMMENT 'MCP配置JSON，格式见文档',
    -- 状态
    `status` TINYINT DEFAULT 1 COMMENT '1=启用 0=禁用',
    -- 统计
    `total_calls` BIGINT DEFAULT 0 COMMENT '总调用次数',
    `failed_calls` BIGINT DEFAULT 0 COMMENT '失败次数',
    -- 时间戳
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- 约束
    UNIQUE KEY `uk_tenant_name` (`tenant_id`, `name`),
    INDEX `idx_tenant_status` (`tenant_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='MCP Server配置表';

-- config 字段示例：
-- SSE 模式:
-- {
--     "transport": "sse",
--     "url": "https://mcp.example.com/sse",
--     "headers": {"Authorization": "Bearer xxx"},
--     "timeout": 30
-- }
-- Streamable HTTP 模式:
-- {
--     "transport": "streamable_http",
--     "url": "https://mcp.example.com/mcp",
--     "headers": {"Authorization": "Bearer xxx"},
--     "timeout": 60
-- }

-- ============================================================================
-- 2. Agent-MCP 绑定表
-- 定义哪些 Agent 可以使用哪些 MCP Server
-- ============================================================================
CREATE TABLE IF NOT EXISTS `agent_mcp_binding` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `agent_id` BIGINT NOT NULL COMMENT 'Agent配置ID',
    `mcp_server_id` BIGINT NOT NULL COMMENT 'MCP Server ID',
    `enabled` BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- 约束
    UNIQUE KEY `uk_agent_mcp` (`agent_id`, `mcp_server_id`),
    INDEX `idx_agent` (`agent_id`),
    INDEX `idx_mcp` (`mcp_server_id`),
    FOREIGN KEY (`mcp_server_id`) REFERENCES `mcp_server`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent-MCP绑定关系表';

-- ============================================================================
-- 3. 角色-工具权限表
-- 细粒度控制角色可以使用哪些工具
-- ============================================================================
CREATE TABLE IF NOT EXISTS `role_tool_permission` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `role_id` BIGINT NOT NULL COMMENT '角色ID',
    `tool_name` VARCHAR(100) NOT NULL COMMENT '工具名称',
    `tool_source` ENUM('BUILTIN', 'MCP', 'CUSTOM') NOT NULL COMMENT '工具来源',
    `permission` TINYINT NOT NULL DEFAULT 1 COMMENT '1=允许 0=禁止',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- 约束
    UNIQUE KEY `uk_role_tool` (`tenant_id`, `role_id`, `tool_name`, `tool_source`),
    INDEX `idx_role` (`role_id`),
    INDEX `idx_tenant_role` (`tenant_id`, `role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色-工具权限表';

-- ============================================================================
-- 4. 审计日志表（通用）
-- 记录所有租户相关操作
-- ============================================================================
CREATE TABLE IF NOT EXISTS `audit_log` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `tenant_id` BIGINT COMMENT '租户ID',
    `user_id` BIGINT COMMENT '用户ID',
    `action_type` VARCHAR(50) NOT NULL COMMENT '操作类型',
    `resource_type` VARCHAR(50) NOT NULL COMMENT '资源类型',
    `resource_id` VARCHAR(100) COMMENT '资源ID',
    `detail` JSON COMMENT '操作详情（JSON）',
    `ip_address` VARCHAR(50) COMMENT 'IP地址',
    `user_agent` VARCHAR(500) COMMENT 'User-Agent',
    `result` TINYINT DEFAULT 1 COMMENT '1=成功 0=失败',
    `error_message` TEXT COMMENT '错误信息',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- 索引
    INDEX `idx_tenant_time` (`tenant_id`, `created_at`),
    INDEX `idx_user_time` (`user_id`, `created_at`),
    INDEX `idx_action` (`action_type`, `created_at`),
    INDEX `idx_resource` (`resource_type`, `resource_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='审计日志表';

-- ============================================================================
-- 5. 工具调用记录表（扩展审计日志）
-- ============================================================================
CREATE TABLE IF NOT EXISTS `tool_execution_log` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `audit_log_id` BIGINT COMMENT '关联审计日志ID',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `user_id` BIGINT NOT NULL COMMENT '用户ID',
    `agent_id` BIGINT COMMENT 'Agent配置ID',
    `tool_name` VARCHAR(100) NOT NULL COMMENT '工具名称',
    `tool_source` ENUM('BUILTIN', 'MCP', 'CUSTOM') NOT NULL COMMENT '工具来源',
    `arguments` JSON COMMENT '调用参数',
    `result` TEXT COMMENT '执行结果',
    `status` TINYINT DEFAULT 1 COMMENT '1=成功 0=失败',
    `error_message` TEXT COMMENT '错误信息',
    `duration_ms` INT COMMENT '执行耗时（毫秒）',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- 索引
    INDEX `idx_tenant_time` (`tenant_id`, `created_at`),
    INDEX `idx_user_time` (`user_id`, `created_at`),
    INDEX `idx_tool` (`tool_name`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工具调用记录表';

-- ============================================================================
-- 6. MCP Server 调用记录表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `mcp_execution_log` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `mcp_server_id` BIGINT NOT NULL COMMENT 'MCP Server ID',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `tool_name` VARCHAR(100) NOT NULL COMMENT '调用的工具名',
    `duration_ms` INT COMMENT '耗时（毫秒）',
    `status` TINYINT DEFAULT 1 COMMENT '1=成功 0=失败',
    `error_message` TEXT COMMENT '错误信息',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- 索引
    INDEX `idx_server_time` (`mcp_server_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='MCP Server调用记录表';

-- ============================================================================
-- 操作类型枚举（供参考）
-- ============================================================================
-- tenant.create / tenant.update / tenant.delete
-- user.create / user.update / user.delete
-- role.create / role.update / role.delete
-- mcp_server.create / mcp_server.update / mcp_server.delete / mcp_server.test / mcp_server.bind
-- agent.create / agent.update / agent.delete / agent.bind
-- role_tool_permission.grant / role_tool_permission.revoke
-- tool.execute / tool.call
