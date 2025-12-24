-- H2 测试库建表脚本（兼容 H2 MODE=MySQL）
DROP TABLE IF EXISTS kb_agent_binding;
DROP TABLE IF EXISTS kb_permission;
DROP TABLE IF EXISTS document_chunk;
DROP TABLE IF EXISTS document;
DROP TABLE IF EXISTS knowledge_base;

CREATE TABLE knowledge_base (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    tenant_id    BIGINT NOT NULL,
    name         VARCHAR(100) NOT NULL,
    description  CLOB,
    type         VARCHAR(20) DEFAULT 'GENERAL',
    embed_model  VARCHAR(100) DEFAULT 'sentence-transformers',
    chunk_config CLOB,
    status       TINYINT DEFAULT 1,
    doc_count    INT DEFAULT 0,
    create_time  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE document (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    tenant_id    BIGINT NOT NULL,
    kb_id        BIGINT NOT NULL,
    name         VARCHAR(255) NOT NULL,
    file_path    VARCHAR(500),
    file_size    BIGINT,
    file_type    VARCHAR(20),
    parse_status VARCHAR(20) DEFAULT 'PENDING',
    chunk_count  INT DEFAULT 0,
    error_msg    CLOB,
    create_time  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE document_chunk (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    doc_id      BIGINT NOT NULL,
    kb_id       BIGINT NOT NULL,
    tenant_id   BIGINT NOT NULL,
    chunk_index INT NOT NULL,
    content     CLOB NOT NULL,
    char_count  INT,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE kb_permission (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    tenant_id   BIGINT NOT NULL,
    kb_id       BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    role        VARCHAR(20) NOT NULL,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (kb_id, user_id)
);

CREATE TABLE kb_agent_binding (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    tenant_id   BIGINT NOT NULL,
    kb_id       BIGINT NOT NULL,
    agent_id    BIGINT NOT NULL,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (kb_id, agent_id)
);

