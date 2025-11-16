-- nexus-auth 用户表
-- 兼容 H2 和 MySQL 语法（H2 mode=MySQL）
CREATE TABLE IF NOT EXISTS `user` (
    `id`          BIGINT NOT NULL AUTO_INCREMENT,
    `tenant_id`   BIGINT NOT NULL COMMENT '租户ID',
    `username`    VARCHAR(50) NOT NULL COMMENT '用户名',
    `email`       VARCHAR(100) COMMENT '邮箱',
    `password`    VARCHAR(100) NOT NULL COMMENT 'BCrypt密码',
    `roles`       VARCHAR(200) DEFAULT 'USER' COMMENT '角色，逗号分隔',
    `status`      TINYINT DEFAULT 1 COMMENT '1=正常 0=禁用',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_tenant_username` (`tenant_id`, `username`)
);
