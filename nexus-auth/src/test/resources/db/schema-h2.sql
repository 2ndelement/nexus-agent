-- H2 测试库建表脚本
DROP TABLE IF EXISTS user;

CREATE TABLE user (
    id          BIGINT NOT NULL AUTO_INCREMENT,
    tenant_id   BIGINT NOT NULL,
    username    VARCHAR(50) NOT NULL,
    email       VARCHAR(100),
    password    VARCHAR(100) NOT NULL,
    roles       VARCHAR(200) DEFAULT 'USER',
    status      TINYINT DEFAULT 1,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uk_tenant_username UNIQUE (tenant_id, username)
);
