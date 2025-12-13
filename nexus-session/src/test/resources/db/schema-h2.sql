-- H2 测试库建表脚本（兼容 H2 MODE=MySQL）
DROP TABLE IF EXISTS message;
DROP TABLE IF EXISTS conversation;

CREATE TABLE conversation (
    id            VARCHAR(64) NOT NULL,
    tenant_id     BIGINT NOT NULL,
    user_id       BIGINT NOT NULL,
    title         VARCHAR(200) DEFAULT '新对话',
    agent_id      BIGINT,
    model         VARCHAR(100) DEFAULT 'MiniMax-M2.5-highspeed',
    status        TINYINT DEFAULT 1,
    message_count INT DEFAULT 0,
    create_time   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
);

CREATE TABLE message (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    conversation_id VARCHAR(64) NOT NULL,
    tenant_id       BIGINT NOT NULL,
    role            VARCHAR(20) NOT NULL,
    content         CLOB NOT NULL,
    tokens          INT DEFAULT 0,
    metadata        CLOB,
    idempotent_key  VARCHAR(128),
    create_time     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
