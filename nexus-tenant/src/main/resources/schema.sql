-- nexus-tenant schema
-- 用于 H2 测试（兼容 MySQL DDL）

CREATE TABLE IF NOT EXISTS `tenant` (
    `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
    `name`        VARCHAR(100) NOT NULL,
    `plan`        VARCHAR(20)  DEFAULT 'FREE',
    `status`      TINYINT      DEFAULT 1,
    `create_time` TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    `update_time` TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `tenant_user` (
    `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
    `tenant_id`   BIGINT       NOT NULL,
    `user_id`     BIGINT       NOT NULL,
    `role`        VARCHAR(20)  DEFAULT 'MEMBER',
    `status`      TINYINT      DEFAULT 1,
    `create_time` TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `uk_tenant_user` UNIQUE (`tenant_id`, `user_id`)
);
