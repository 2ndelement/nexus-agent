-- ============================================================================
-- NexusAgent 数据库初始化 V1
-- 基础表结构
-- ============================================================================

-- ============================================================================
-- 1. 租户表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `tenant` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `name` VARCHAR(100) NOT NULL COMMENT '租户名称',
    `code` VARCHAR(50) NOT NULL COMMENT '租户代码',
    `status` TINYINT DEFAULT 1 COMMENT '1=启用 0=禁用',
    `config` JSON COMMENT '租户配置',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='租户表';

-- ============================================================================
-- 2. 用户表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `user` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `username` VARCHAR(100) NOT NULL COMMENT '用户名',
    `password` VARCHAR(255) COMMENT '密码（哈希）',
    `nickname` VARCHAR(100) COMMENT '昵称',
    `email` VARCHAR(200) COMMENT '邮箱',
    `phone` VARCHAR(20) COMMENT '手机号',
    `avatar` VARCHAR(500) COMMENT '头像URL',
    `status` TINYINT DEFAULT 1 COMMENT '1=启用 0=禁用',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_tenant_username` (`tenant_id`, `username`),
    INDEX `idx_tenant` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ============================================================================
-- 3. 角色表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `role` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `name` VARCHAR(100) NOT NULL COMMENT '角色名称',
    `code` VARCHAR(50) NOT NULL COMMENT '角色代码',
    `description` VARCHAR(500) COMMENT '描述',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_tenant_code` (`tenant_id`, `code`),
    INDEX `idx_tenant` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色表';

-- ============================================================================
-- 4. 用户角色关联表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `user_role` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT NOT NULL,
    `role_id` BIGINT NOT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_user_role` (`user_id`, `role_id`),
    INDEX `idx_user` (`user_id`),
    INDEX `idx_role` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户角色关联表';

-- ============================================================================
-- 5. Agent 配置表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `agent_config` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `name` VARCHAR(100) NOT NULL COMMENT 'Agent名称',
    `description` VARCHAR(500) COMMENT '描述',
    `system_prompt` TEXT COMMENT '系统提示词',
    `model` VARCHAR(100) DEFAULT 'gpt-4o' COMMENT '模型名称',
    `temperature` DECIMAL(3,2) DEFAULT 0.7 COMMENT '温度参数',
    `max_tokens` INT DEFAULT 4096 COMMENT '最大Token数',
    `tools_enabled` JSON COMMENT '启用的工具列表',
    `status` TINYINT DEFAULT 1 COMMENT '1=启用 0=禁用',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_tenant` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent配置表';

-- ============================================================================
-- 6. 会话表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `conversation` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `conversation_id` VARCHAR(100) NOT NULL COMMENT '会话UUID',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `user_id` BIGINT NOT NULL COMMENT '用户ID',
    `agent_id` BIGINT COMMENT 'Agent配置ID',
    `title` VARCHAR(200) COMMENT '会话标题',
    `status` TINYINT DEFAULT 1 COMMENT '1=进行中 2=已结束',
    `message_count` INT DEFAULT 0 COMMENT '消息数量',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_conversation_id` (`conversation_id`),
    INDEX `idx_tenant_user` (`tenant_id`, `user_id`),
    INDEX `idx_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话表';

-- ============================================================================
-- 7. 消息表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `message` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `conversation_id` VARCHAR(100) NOT NULL COMMENT '会话ID',
    `role` ENUM('user', 'assistant', 'system', 'tool') NOT NULL COMMENT '消息角色',
    `content` TEXT COMMENT '消息内容',
    `tool_calls` JSON COMMENT '工具调用（AI回复）',
    `tool_call_id` VARCHAR(100) COMMENT '工具调用ID（工具回复）',
    `tokens_input` INT COMMENT '输入Token数',
    `tokens_output` INT COMMENT '输出Token数',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_conversation` (`conversation_id`),
    INDEX `idx_conversation_time` (`conversation_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消息表';

-- ============================================================================
-- 8. 工具注册表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `tool` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `name` VARCHAR(100) NOT NULL COMMENT '工具名称',
    `display_name` VARCHAR(100) COMMENT '显示名称',
    `description` VARCHAR(500) COMMENT '描述',
    `source` ENUM('BUILTIN', 'MCP', 'CUSTOM') NOT NULL DEFAULT 'BUILTIN' COMMENT '来源',
    `category` VARCHAR(50) COMMENT '分类',
    `schema` JSON COMMENT '参数Schema（OpenAI格式）',
    `endpoint` VARCHAR(500) COMMENT '执行端点（MCP/自定义工具）',
    `config` JSON COMMENT '工具配置',
    `status` TINYINT DEFAULT 1 COMMENT '1=启用 0=禁用',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工具注册表';

-- ============================================================================
-- 9. 知识库表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `knowledge_base` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `name` VARCHAR(100) NOT NULL COMMENT '知识库名称',
    `description` VARCHAR(500) COMMENT '描述',
    `embedding_model` VARCHAR(100) DEFAULT 'text-embedding-3-small' COMMENT 'Embedding模型',
    `chunk_size` INT DEFAULT 500 COMMENT '分块大小',
    `chunk_overlap` INT DEFAULT 50 COMMENT '分块重叠',
    `doc_count` INT DEFAULT 0 COMMENT '文档数量',
    `status` TINYINT DEFAULT 1 COMMENT '1=启用 0=禁用',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_tenant` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库表';

-- ============================================================================
-- 10. 知识库文档表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `knowledge_doc` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `kb_id` BIGINT NOT NULL COMMENT '知识库ID',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `title` VARCHAR(200) NOT NULL COMMENT '文档标题',
    `file_path` VARCHAR(500) COMMENT '文件路径',
    `file_type` VARCHAR(20) COMMENT '文件类型',
    `file_size` BIGINT COMMENT '文件大小',
    `chunk_count` INT DEFAULT 0 COMMENT '分块数量',
    `status` ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending' COMMENT '处理状态',
    `error_message` TEXT COMMENT '错误信息',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_kb` (`kb_id`),
    INDEX `idx_tenant` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库文档表';

-- ============================================================================
-- 11. 计费记录表
-- ============================================================================
CREATE TABLE IF NOT EXISTS `billing_record` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `user_id` BIGINT COMMENT '用户ID',
    `conversation_id` VARCHAR(100) COMMENT '会话ID',
    `model` VARCHAR(100) COMMENT '模型名称',
    `tokens_input` INT DEFAULT 0 COMMENT '输入Token数',
    `tokens_output` INT DEFAULT 0 COMMENT '输出Token数',
    `cost` DECIMAL(10,6) DEFAULT 0 COMMENT '费用',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_tenant_time` (`tenant_id`, `created_at`),
    INDEX `idx_user_time` (`user_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='计费记录表';

-- ============================================================================
-- 初始化数据
-- ============================================================================

-- 创建默认租户
INSERT INTO `tenant` (`id`, `name`, `code`, `status`) VALUES
(1, '默认租户', 'default', 1)
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`);

-- 创建默认管理员用户 (密码: admin123 的 bcrypt 哈希)
INSERT INTO `user` (`id`, `tenant_id`, `username`, `password`, `nickname`, `status`) VALUES
(1, 1, 'admin', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iAt6Z5EH', '管理员', 1)
ON DUPLICATE KEY UPDATE `username` = VALUES(`username`);

-- 创建默认角色
INSERT INTO `role` (`id`, `tenant_id`, `name`, `code`, `description`) VALUES
(1, 1, '管理员', 'admin', '系统管理员，拥有所有权限'),
(2, 1, '普通用户', 'user', '普通用户，可以使用 Agent 对话')
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`);

-- 关联用户角色
INSERT INTO `user_role` (`user_id`, `role_id`) VALUES
(1, 1)
ON DUPLICATE KEY UPDATE `user_id` = VALUES(`user_id`);

-- 创建默认 Agent 配置
INSERT INTO `agent_config` (`id`, `tenant_id`, `name`, `description`, `system_prompt`, `model`) VALUES
(1, 1, '通用助手', 'NexusAgent 默认助手', '你是一个有帮助的AI助手。请用中文回答问题。', 'gpt-4o')
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`);

-- 注册内置工具
INSERT INTO `tool` (`name`, `display_name`, `description`, `source`, `category`, `schema`) VALUES
('calculator', '计算器', '执行数学计算', 'BUILTIN', 'utility', '{"type": "function", "function": {"name": "calculator", "description": "执行数学计算", "parameters": {"type": "object", "properties": {"expression": {"type": "string", "description": "数学表达式"}}, "required": ["expression"]}}}'),
('web_search', '网页搜索', '搜索互联网信息', 'BUILTIN', 'search', '{"type": "function", "function": {"name": "web_search", "description": "搜索互联网信息", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "搜索关键词"}}, "required": ["query"]}}}'),
('code_execute', '代码执行', '在沙箱中执行代码', 'BUILTIN', 'code', '{"type": "function", "function": {"name": "code_execute", "description": "在沙箱中执行Python代码", "parameters": {"type": "object", "properties": {"code": {"type": "string", "description": "要执行的Python代码"}}, "required": ["code"]}}}')
ON DUPLICATE KEY UPDATE `description` = VALUES(`description`);

SELECT 'V1 initialization completed' AS status;
