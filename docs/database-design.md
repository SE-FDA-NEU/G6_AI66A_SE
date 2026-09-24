# DocuMind — Database Design

> Phiên bản: Sprint 2 baseline  
> Engine: **MySQL 8.x**  
> ORM: SQLAlchemy 2.x + PyMySQL driver

---

## ERD (Entity Relationship Diagram)

```
┌──────────────────┐         ┌──────────────────────────┐
│      users       │         │         folders          │
├──────────────────┤         ├──────────────────────────┤
│ id (PK)          │◄──┐     │ id (PK)                  │
│ email (UNIQUE)   │   │     │ owner_id (FK → users.id) │
│ password_hash    │   │     │ name                     │
│ created_at       │   │     │ created_at               │
└──────────────────┘   │     └───────────┬──────────────┘
                        │                │
                        │     ┌──────────▼──────────────────────────────┐
                        │     │               documents                  │
                        │     ├─────────────────────────────────────────┤
                        └─────┤ id (PK)                                  │
                              │ owner_id (FK → users.id)                 │
                              │ folder_id (FK → folders.id, nullable)    │
                              │ original_filename                        │
                              │ storage_path                             │
                              │ file_format  -- PDF | DOCX | PPTX        │
                              │ file_size_bytes                          │
                              │ page_count                               │
                              │ ai_label                                 │
                              │ ai_confidence  -- 0.0–1.0               │
                              │ review_state   -- confirmed|needs_review │
                              │ user_label     -- nullable               │
                              │ extracted_text (JSON)                    │
                              │ last_accessed_at   -- BR06               │
                              │ expires_at         -- BR06               │
                              │ created_at                               │
                              └───────────┬─────────────────────────────┘
                                          │ 1
                                          │
                                          │ N
                              ┌───────────▼─────────────────────────────┐
                              │                 jobs                     │
                              ├─────────────────────────────────────────┤
                              │ id (PK, UUID)                            │
                              │ owner_id (FK → users.id)                 │
                              │ mode  -- bullet|table|concept   │
                              │ status                                   │
                              │   pending|processing|completed           │
                              │   |failed|timed_out                      │
                              │ file_count                               │
                              │ completed_count                          │
                              │ created_at                               │
                              │ finished_at                              │
                              └───────────┬─────────────────────────────┘
                                          │ 1
                          ┌───────────────┴───────────────┐
                          │ N                             │ N
              ┌───────────▼──────────────┐   ┌───────────▼──────────────────┐
              │         job_files        │   │          citations            │
              ├──────────────────────────┤   ├──────────────────────────────┤
              │ id (PK)                  │   │ id (PK)                      │
              │ job_id (FK → jobs.id)    │   │ job_id (FK → jobs.id)        │
              │ document_id (FK)         │   │ document_id (FK)             │
              │ status                   │   │ claim_text                   │
              │   pending|processing     │   │ doc_name                     │
              │   |completed|failed      │   │ page                         │
              │   |timed_out             │   │ text_span  -- nullable       │
              │ attempt_count  -- BR02   │   │ unverified  -- bool, BR05    │
              │ timeout_seconds  -- BR02 │   │ created_at                   │
              │ error_message            │   └──────────────────────────────┘
              │ created_at               │
              └──────────────────────────┘
```

---

## Chi tiết từng bảng

### `users`

| Column          | Type         | Constraint             | Ghi chú           |
| --------------- | ------------ | ---------------------- | ----------------- |
| `id`            | UUID         | PK                     | Auto-generated    |
| `email`         | VARCHAR(255) | UNIQUE NOT NULL        | Dùng làm username |
| `password_hash` | VARCHAR(255) | NOT NULL               | bcrypt            |
| `created_at`    | TIMESTAMP    | NOT NULL DEFAULT now() |                   |

---

### `folders`

| Column       | Type         | Constraint             | Ghi chú                |
| ------------ | ------------ | ---------------------- | ---------------------- |
| `id`         | UUID         | PK                     |                        |
| `owner_id`   | UUID         | FK → users.id NOT NULL |                        |
| `name`       | VARCHAR(100) | NOT NULL               | Ví dụ: "Economics 101" |
| `created_at` | TIMESTAMP    | NOT NULL DEFAULT now() |                        |

> User tự tạo folder. AI không bao giờ tạo hoặc thay đổi folder (BR03).

---

### `documents`

| Column              | Type         | Constraint                   | Ghi chú                               |
| ------------------- | ------------ | ---------------------------- | ------------------------------------- |
| `id`                | UUID         | PK                           |                                       |
| `owner_id`          | UUID         | FK → users.id NOT NULL       | Ownership check (BR07)                |
| `folder_id`         | UUID         | FK → folders.id **NULLABLE** | NULL = chưa xếp folder                |
| `original_filename` | VARCHAR(255) | NOT NULL                     |                                       |
| `storage_path`      | TEXT         | NOT NULL                     | Path trên disk/S3                     |
| `file_format`       | VARCHAR(10)  | NOT NULL                     | `PDF`, `DOCX`, `PPTX` (BR01)          |
| `file_size_bytes`   | BIGINT       | NOT NULL                     | Validate ≤ 5MB (BR01)                 |
| `page_count`        | INT          | NULLABLE                     | Điền sau khi parse xong               |
| `ai_label`          | VARCHAR(100) | NULLABLE                     | Kết quả từ model                      |
| `ai_confidence`     | FLOAT        | NULLABLE                     | 0.0 – 1.0 (BR03: ≥ 0.8 = confirmed)   |
| `review_state`      | VARCHAR(20)  | DEFAULT `needs_review`       | `confirmed` hoặc `needs_review`       |
| `user_label`        | VARCHAR(100) | NULLABLE                     | User tự chọn, không ghi đè `ai_label` |
| `extracted_text`    | JSON         | NULLABLE                     | `[{"page": 1, "text": "..."}]`        |
| `last_accessed_at`  | TIMESTAMP    | NOT NULL DEFAULT now()       | Cập nhật mỗi lần mở/download (BR06)   |
| `expires_at`        | TIMESTAMP    | NOT NULL                     | `last_accessed_at + 30 days` (BR06)   |
| `created_at`        | TIMESTAMP    | NOT NULL DEFAULT now()       |                                       |

**Index:**

```sql
CREATE INDEX idx_documents_owner ON documents(owner_id);
CREATE INDEX idx_documents_expires ON documents(expires_at);  -- cho cleanup job BR06
CREATE INDEX idx_documents_label ON documents(ai_label);       -- cho label filter
```

---

### `jobs`

| Column            | Type        | Constraint                 | Ghi chú                               |
| ----------------- | ----------- | -------------------------- | ------------------------------------- |
| `id`              | UUID        | PK                         | Trả về client ngay sau POST /upload   |
| `owner_id`        | UUID        | FK → users.id NOT NULL     | Ownership check                       |
| `mode`            | VARCHAR(20) | NOT NULL                   | `bullet`, `contract_table`, `concept` |
| `status`          | VARCHAR(20) | NOT NULL DEFAULT `pending` | Xem enum bên dưới                     |
| `file_count`      | INT         | NOT NULL                   | Tổng số file trong batch              |
| `completed_count` | INT         | NOT NULL DEFAULT 0         | Dùng cho progress `3/5`               |
| `created_at`      | TIMESTAMP   | NOT NULL DEFAULT now()     |                                       |
| `finished_at`     | TIMESTAMP   | NULLABLE                   | Điền khi status = terminal            |

**Status enum:** `pending → processing → completed | failed | timed_out`

---

### `job_files`

Mỗi row = 1 file trong 1 job (batch 5 file → 5 rows).

| Column            | Type        | Constraint                 | Ghi chú                               |
| ----------------- | ----------- | -------------------------- | ------------------------------------- |
| `id`              | UUID        | PK                         |                                       |
| `job_id`          | UUID        | FK → jobs.id NOT NULL      |                                       |
| `document_id`     | UUID        | FK → documents.id NOT NULL |                                       |
| `status`          | VARCHAR(20) | NOT NULL DEFAULT `pending` | Giống jobs.status enum                |
| `attempt_count`   | INT         | NOT NULL DEFAULT 0         | Tối đa 3 lần (BR02)                   |
| `timeout_seconds` | INT         | NULLABLE                   | `30 + 3 × page_count`, max 300 (BR02) |
| `error_message`   | TEXT        | NULLABLE                   | Lý do fail/timeout                    |
| `created_at`      | TIMESTAMP   | NOT NULL DEFAULT now()     |                                       |

---

### `citations`

| Column        | Type         | Constraint                 | Ghi chú                                |
| ------------- | ------------ | -------------------------- | -------------------------------------- |
| `id`          | UUID         | PK                         |                                        |
| `job_id`      | UUID         | FK → jobs.id NOT NULL      |                                        |
| `document_id` | UUID         | FK → documents.id NOT NULL |                                        |
| `claim_text`  | TEXT         | NOT NULL                   | Đoạn text trích dẫn                    |
| `doc_name`    | VARCHAR(255) | NOT NULL                   | Tên hiển thị (BR05)                    |
| `page`        | INT          | NULLABLE                   | NULL nếu không xác định được           |
| `text_span`   | TEXT         | NULLABLE                   | Đoạn nguyên văn để highlight           |
| `unverified`  | TINYINT(1)   | NOT NULL DEFAULT 0         | 1 → hiển thị badge `Unverified` (BR05) |
| `created_at`  | TIMESTAMP    | NOT NULL DEFAULT now()     |                                        |

**Index:**

```sql
CREATE INDEX idx_citations_job ON citations(job_id);
```

---

## Business Rules → Database mapping

| BR   | Rule                                                              | Enforced where                                                              |
| ---- | ----------------------------------------------------------------- | --------------------------------------------------------------------------- |
| BR01 | File format + size ≤ 5MB + count ≤ 5                              | `documents.file_format`, `file_size_bytes`; validated before INSERT         |
| BR02 | Timeout = 30 + 3×pages, max 300s, retry ≤ 2                       | `job_files.timeout_seconds`, `attempt_count`                                |
| BR03 | AI label confidence ≥ 0.8 → confirmed; folder never auto-assigned | `documents.ai_confidence`, `review_state`; `folder_id` only updated by user |
| BR04 | Summary ≤ 1000 words                                              | Enforced in LLM prompt + post-processing, not in DB                         |
| BR05 | Every verified fact must have source                              | `citations.unverified`; NULL `page` + `text_span` → unverified              |
| BR06 | 30-day expiry, reset on access                                    | `documents.last_accessed_at`, `expires_at`; background cleanup job          |
| BR07 | User sees only own data                                           | `owner_id` FK on all tables; checked in every API handler                   |

---

## SQL — Create Tables (MySQL 8.x)

```sql
CREATE TABLE users (
    id          VARCHAR(36)  PRIMARY KEY,
    username    VARCHAR(100) NOT NULL UNIQUE,
    email       VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE folders (
    id          VARCHAR(36)  PRIMARY KEY,
    owner_id    VARCHAR(36)  NOT NULL,
    name        VARCHAR(100) NOT NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE documents (
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
    FOREIGN KEY (owner_id)  REFERENCES users(id),
    FOREIGN KEY (folder_id) REFERENCES folders(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_documents_owner   ON documents(owner_id);
CREATE INDEX idx_documents_expires ON documents(expires_at);
CREATE INDEX idx_documents_label   ON documents(ai_label);

CREATE TABLE jobs (
    id               VARCHAR(36) PRIMARY KEY,
    owner_id         VARCHAR(36) NOT NULL,
    mode             VARCHAR(20) NOT NULL,          -- bullet|table|concept
    status           VARCHAR(20) NOT NULL DEFAULT 'pending',
    file_count       INT         NOT NULL,
    completed_count  INT         NOT NULL DEFAULT 0,
    created_at       DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at      DATETIME    DEFAULT NULL,
    FOREIGN KEY (owner_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE job_files (
    id               VARCHAR(36) PRIMARY KEY,
    job_id           VARCHAR(36) NOT NULL,
    document_id      VARCHAR(36) NOT NULL,
    status           VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempt_count    INT         NOT NULL DEFAULT 0,
    timeout_seconds  INT         DEFAULT NULL,
    error_message    TEXT        DEFAULT NULL,
    created_at       DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id)      REFERENCES jobs(id),
    FOREIGN KEY (document_id) REFERENCES documents(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE citations (
    id          VARCHAR(36)  PRIMARY KEY,
    job_id      VARCHAR(36)  NOT NULL,
    document_id VARCHAR(36)  NOT NULL,
    claim_text  TEXT         NOT NULL,
    doc_name    VARCHAR(255) NOT NULL,
    page        INT          DEFAULT NULL,
    text_span   TEXT         DEFAULT NULL,
    unverified  TINYINT(1)   NOT NULL DEFAULT 0,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id)      REFERENCES jobs(id),
    FOREIGN KEY (document_id) REFERENCES documents(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_citations_job ON citations(job_id);
```
