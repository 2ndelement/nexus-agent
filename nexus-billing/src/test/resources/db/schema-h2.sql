-- H2 测试库建表脚本

DROP TABLE IF EXISTS usage_daily;
DROP TABLE IF EXISTS tenant_quota;
DROP TABLE IF EXISTS plan;

CREATE TABLE plan (
    id                BIGINT NOT NULL AUTO_INCREMENT,
    name              VARCHAR(50) NOT NULL,
    display_name      VARCHAR(100),
    max_users         INT DEFAULT 5,
    max_agents        INT DEFAULT 3,
    max_api_calls_day INT DEFAULT 1000,
    max_tokens_day    BIGINT DEFAULT 100000,
    max_kb_size_mb    INT DEFAULT 100,
    price_monthly     DECIMAL(10,2) DEFAULT 0.00,
    create_time       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uk_plan_name UNIQUE (name)
);

CREATE TABLE tenant_quota (
    id           BIGINT NOT NULL AUTO_INCREMENT,
    tenant_id    BIGINT NOT NULL,
    plan_id      BIGINT NOT NULL,
    extra_calls  INT DEFAULT 0,
    extra_tokens BIGINT DEFAULT 0,
    valid_until  DATE,
    create_time  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uk_tenant_quota_tenant UNIQUE (tenant_id)
);

CREATE TABLE usage_daily (
    id            BIGINT NOT NULL AUTO_INCREMENT,
    tenant_id     BIGINT NOT NULL,
    stat_date     DATE NOT NULL,
    api_calls     INT DEFAULT 0,
    input_tokens  BIGINT DEFAULT 0,
    output_tokens BIGINT DEFAULT 0,
    model         VARCHAR(100),
    create_time   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uk_tenant_date_model UNIQUE (tenant_id, stat_date, model)
);

-- 预置测试套餐数据
INSERT INTO plan (name, display_name, max_users, max_agents, max_api_calls_day, max_tokens_day, max_kb_size_mb, price_monthly) VALUES
('FREE',       '免费版',   5,    3,     10,   1000,   100, 0.00),
('PRO',        '专业版',  50,   20,   1000, 100000,  1024, 99.00),
('ENTERPRISE', '企业版', 500, 1000, 100000, 10000000, 10240, 999.00);
