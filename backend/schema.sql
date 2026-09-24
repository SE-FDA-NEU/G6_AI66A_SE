-- DocuMind Database Schema (MySQL)
-- Chạy file này trực tiếp trong MySQL Client (Workbench, TablePlus...)

CREATE DATABASE IF NOT EXISTS documind_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE documind_db;

CREATE TABLE IF NOT EXISTS users (
    id          VARCHAR(36)  PRIMARY KEY,
    email       VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS folders (
    id          VARCHAR(36)  PRIMARY KEY,
    owner_id    VARCHAR(36)  NOT NULL,
    name        VARCHAR(100) NOT NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS documents (
    id                VARCHAR(36)  PRIMARY KEY,
    owner_id          VARCHAR(36)  NOT NULL,
    folder_id         VARCHAR(36)  DEFAULT NULL,
    original_filename VARCHAR(255) NOT NULL,
    storage_path      TEXT         NOT NULL,
    file_format       VARCHAR(10)  NOT NULL,          -- PDF | DOCX | PPTX
    file_size_bytes   BIGINT       NOT NULL,
    page_count        INT          DEFAULT NULL,
    ai_label          VARCHAR(100) DEFAULT NULL,
    ai_confidence     FLOAT        DEFAULT NULL,      -- 0.0–1.0
    review_state      VARCHAR(20)  NOT NULL DEFAULT 'needs_review',
    user_label        VARCHAR(100) DEFAULT NULL,
    extracted_text    JSON         DEFAULT NULL,      -- [{page, text}]
    last_accessed_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at        DATETIME     NOT NULL,
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id)  REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_documents_owner   ON documents(owner_id);
CREATE INDEX idx_documents_expires ON documents(expires_at);
CREATE INDEX idx_documents_label   ON documents(ai_label);

CREATE TABLE IF NOT EXISTS jobs (
    id               VARCHAR(36) PRIMARY KEY,
    owner_id         VARCHAR(36) NOT NULL,
    mode             VARCHAR(20) NOT NULL,          -- bullet|contract_table|concept
    status           VARCHAR(20) NOT NULL DEFAULT 'pending',
    file_count       INT         NOT NULL,
    completed_count  INT         NOT NULL DEFAULT 0,
    created_at       DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at      DATETIME    DEFAULT NULL,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS job_files (
    id               VARCHAR(36) PRIMARY KEY,
    job_id           VARCHAR(36) NOT NULL,
    document_id      VARCHAR(36) NOT NULL,
    status           VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempt_count    INT         NOT NULL DEFAULT 0,
    timeout_seconds  INT         DEFAULT NULL,
    error_message    TEXT        DEFAULT NULL,
    created_at       DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id)      REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS citations (
    id          VARCHAR(36)  PRIMARY KEY,
    job_id      VARCHAR(36)  NOT NULL,
    document_id VARCHAR(36)  NOT NULL,
    claim_text  TEXT         NOT NULL,
    doc_name    VARCHAR(255) NOT NULL,
    page        INT          DEFAULT NULL,
    text_span   TEXT         DEFAULT NULL,
    unverified  TINYINT(1)   NOT NULL DEFAULT 0,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id)      REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_citations_job ON citations(job_id);
