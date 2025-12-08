-- 生产环境建表脚本（MySQL）

-- 套餐定义
CREATE TABLE IF NOT EXISTS `plan` (
  `id`               BIGINT AUTO_INCREMENT PRIMARY KEY,
  `name`             VARCHAR(50) NOT NULL UNIQUE COMMENT 'FREE/PRO/ENTERPRISE',
  `display_name`     VARCHAR(100),
  `max_users`        INT DEFAULT 5,
  `max_agents`       INT DEFAULT 3,
  `max_api_calls_day` INT DEFAULT 1000 COMMENT '每日 API 调用次数上限',
  `max_tokens_day`   BIGINT DEFAULT 100000 COMMENT '每日 Token 上限',
  `max_kb_size_mb`   INT DEFAULT 100 COMMENT '知识库容量上限(MB)',
  `price_monthly`    DECIMAL(10,2) DEFAULT 0.00,
  `create_time`      DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 租户配额
CREATE TABLE IF NOT EXISTS `tenant_quota` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `tenant_id`   BIGINT NOT NULL UNIQUE,
  `plan_id`     BIGINT NOT NULL,
  `extra_calls` INT DEFAULT 0 COMMENT '额外购买的调用次数',
  `extra_tokens` BIGINT DEFAULT 0,
  `valid_until` DATE COMMENT '套餐到期日，NULL=永久',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 用量记录（按天汇总，不存明细）
CREATE TABLE IF NOT EXISTS `usage_daily` (
  `id`           BIGINT AUTO_INCREMENT PRIMARY KEY,
  `tenant_id`    BIGINT NOT NULL,
  `stat_date`    DATE NOT NULL COMMENT '统计日期',
  `api_calls`    INT DEFAULT 0,
  `input_tokens` BIGINT DEFAULT 0,
  `output_tokens` BIGINT DEFAULT 0,
  `model`        VARCHAR(100) COMMENT '模型名称',
  `create_time`  DATETIME DEFAULT CURRENT_TIMESTAMP,
  `update_time`  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_tenant_date_model` (`tenant_id`, `stat_date`, `model`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 预置套餐数据
INSERT IGNORE INTO `plan` (name, display_name, max_users, max_agents, max_api_calls_day, max_tokens_day, max_kb_size_mb, price_monthly) VALUES
('FREE',       '免费版',   5,    3,     1000,    100000,   100, 0.00),
('PRO',        '专业版',  50,   20,    10000,  2000000,  1024, 99.00),
('ENTERPRISE', '企业版', 500, 1000,  100000, 100000000, 10240, 999.00);
