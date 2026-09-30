# DocuMind — System Design

> Phiên bản: Sprint 2 baseline  
> Engine: **MySQL 8.x**  
> ORM: SQLAlchemy 2.x + PyMySQL driver

---

## 3.1 Architecture

```text
┌───────────────────┐    HTTP (JSON/JWT)    ┌─────────────────────────┐
│     Browser       │ ────────────────────► │      FastAPI App        │
│ (Swagger/React)   │ ◄──────────────────── │      backend/app        │
└───────────────────┘     JSON response     └───────────┬─────────────┘
                                                        │ function calls
                                                        ▼
                                            ┌─────────────────────────┐
                                            │      Core Services      │
                                            │   auth, jobs, upload    │
                                            │   (enforces BR1–BR7)    │
                                            └───────────┬─────────────┘
                                                        │ SQL (SQLAlchemy)
                                                        ▼
                                            ┌─────────────────────────┐
                                            │     MySQL Database      │
                                            │       documind_db       │
                                            └─────────────────────────┘
```

## 3.2 Data model

### ERD (Entity Relationship Diagram)

![ERD Diagram](images/ERD.drawio.png)

---

## Chi tiết từng bảng

### `users`

| Column          | Type         | Constraint             | Ghi chú        |
| --------------- | ------------ | ---------------------- | -------------- |
| `id`            | INT          | PK                     | Auto Increment |
| `username`      | VARCHAR(100) | UNIQUE NOT NULL        |                |
| `email`         | VARCHAR(255) | UNIQUE NOT NULL        |                |
| `password_hash` | VARCHAR(255) | NOT NULL               | bcrypt         |
| `created_at`    | TIMESTAMP    | NOT NULL DEFAULT now() |                |

---

### `folders`

| Column       | Type         | Constraint             | Ghi chú                |
| ------------ | ------------ | ---------------------- | ---------------------- |
| `id`         | INT          | PK                     |                        |
| `owner_id`   | INT          | FK → users.id NOT NULL |                        |
| `name`       | VARCHAR(100) | NOT NULL               | Ví dụ: "Economics 101" |
| `created_at` | TIMESTAMP    | NOT NULL DEFAULT now() |                        |

> User tự tạo folder. AI không bao giờ tạo hoặc thay đổi folder (BR03).

---

### `documents`

| Column              | Type                              | Constraint                   | Ghi chú                               |
| ------------------- | --------------------------------- | ---------------------------- | ------------------------------------- |
| `id`                | INT                               | PK                           |                                       |
| `owner_id`          | INT                               | FK → users.id NOT NULL       | Ownership check (BR07)                |
| `folder_id`         | INT                               | FK → folders.id **NULLABLE** | NULL = chưa xếp folder                |
| `original_filename` | VARCHAR(255)                      | NOT NULL                     |                                       |
| `storage_path`      | TEXT                              | NOT NULL                     | Path trên disk/S3                     |
| `file_format`       | ENUM('PDF', 'DOCX', 'PPTX')       | NOT NULL                     | `PDF`, `DOCX`, `PPTX` (BR01)          |
| `file_size_bytes`   | BIGINT                            | NOT NULL                     | Validate ≤ 5MB (BR01)                 |
| `page_count`        | INT                               | NULLABLE                     | Điền sau khi parse xong               |
| `ai_label`          | VARCHAR(100)                      | NULLABLE                     | Kết quả từ model                      |
| `ai_confidence`     | FLOAT                             | NULLABLE                     | 0.0 – 1.0 (BR03: ≥ 0.8 = confirmed)   |
| `review_state`      | ENUM('confirmed', 'needs_review') | DEFAULT `needs_review`       | `confirmed` hoặc `needs_review`       |
| `user_label`        | VARCHAR(100)                      | NULLABLE                     | User tự chọn, không ghi đè `ai_label` |
| `extracted_text`    | JSON                              | NULLABLE                     | `[{"page": 1, "text": "..."}]`        |
| `last_accessed_at`  | TIMESTAMP                         | NOT NULL DEFAULT now()       | Cập nhật mỗi lần mở/download (BR06)   |
| `expires_at`        | TIMESTAMP                         | NOT NULL                     | `last_accessed_at + 30 days` (BR06)   |
| `created_at`        | TIMESTAMP                         | NOT NULL DEFAULT now()       |                                       |

**Index:**

```sql
CREATE INDEX idx_documents_owner ON documents(owner_id);
CREATE INDEX idx_documents_expires ON documents(expires_at);
CREATE INDEX idx_documents_label ON documents(ai_label);
```

---

### `jobs`

| Column            | Type                                                              | Constraint                 | Ghi chú                             |
| ----------------- | ----------------------------------------------------------------- | -------------------------- | ----------------------------------- |
| `id`              | INT                                                               | PK                         | Trả về client ngay sau POST /upload |
| `owner_id`        | INT                                                               | FK → users.id NOT NULL     | Ownership check                     |
| `mode`            | ENUM('bullet', 'table', 'concept')                                | NOT NULL                   | `bullet`, `table`, `concept`        |
| `status`          | ENUM('pending', 'processing', 'completed', 'failed', 'timed_out') | NOT NULL DEFAULT `pending` | Xem enum bên dưới                   |
| `file_count`      | INT                                                               | NOT NULL                   | Tổng số file trong batch            |
| `completed_count` | INT                                                               | NOT NULL DEFAULT 0         | Dùng cho progress `3/5`             |
| `result_data`     | JSON                                                              | NULLABLE                   | Lưu kết quả đầu ra của Job          |
| `created_at`      | TIMESTAMP                                                         | NOT NULL DEFAULT now()     |                                     |
| `finished_at`     | TIMESTAMP                                                         | NULLABLE                   | Điền khi status = terminal          |

**Status enum:** `pending → processing → completed | failed | timed_out`

---

### `job_files`

Mỗi row = 1 file trong 1 job (batch 5 file → 5 rows).

| Column            | Type                                                              | Constraint                 | Ghi chú                               |
| ----------------- | ----------------------------------------------------------------- | -------------------------- | ------------------------------------- |
| `id`              | INT                                                               | PK                         |                                       |
| `job_id`          | INT                                                               | FK → jobs.id NOT NULL      |                                       |
| `document_id`     | INT                                                               | FK → documents.id NOT NULL |                                       |
| `status`          | ENUM('pending', 'processing', 'completed', 'failed', 'timed_out') | NOT NULL DEFAULT `pending` | Giống jobs.status enum                |
| `attempt_count`   | INT                                                               | NOT NULL DEFAULT 0         | Tối đa 3 lần (BR02)                   |
| `timeout_seconds` | INT                                                               | NULLABLE                   | `30 + 3 × page_count`, max 300 (BR02) |
| `error_message`   | TEXT                                                              | NULLABLE                   | Lý do fail/timeout                    |
| `created_at`      | TIMESTAMP                                                         | NOT NULL DEFAULT now()     |                                       |

---

### `citations`

| Column        | Type         | Constraint                 | Ghi chú                                |
| ------------- | ------------ | -------------------------- | -------------------------------------- |
| `id`          | INT          | PK                         |                                        |
| `job_id`      | INT          | FK → jobs.id NOT NULL      |                                        |
| `document_id` | INT          | FK → documents.id NOT NULL |                                        |
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
## 3.3 API design

| Method | Path | Input | Success | Errors |
| :--- | :--- | :--- | :--- | :--- |
| **POST** | `/auth/login` | Form:<br>`username`, `password` | `200` &middot; `access_token`, `token_type` | `401` invalid credentials;<br>`422` missing form fields |
| **POST** | `/upload` | Multipart: `files` (1–5 PDF/DOCX/PPTX files), `mode` (`bullet`, `table`, `concept`) | `202` &middot; `job_id`, `status: pending`, accepted document IDs | `401` no valid token (**BR07**);<br>`413` file > 5 MB or batch > 50 MB (**BR01**);<br>`422` invalid format, count or mode (**BR01**) |
| **GET** | `/documents` | Query:<br>`folder_id?`, `label?`, `review_state?` | `200` &middot; current user's document list with suggested labels, folder and processing status | `401` unauthenticated (**BR07**);<br>`422` invalid filter |
| **GET** | `/documents/{document_id}` | Path:<br>`document_id` | `200` &middot; document metadata, AI label/confidence, user label, folder, page count, expiry | `401` unauthenticated;<br>`404` absent or not owned (**BR07**) |
| **GET** | `/documents/{document_id}/file` | Path: `document_id`;<br>query: `page?` | `200` &middot; original file for the reader; `page` selects the initial view | `401` unauthenticated;<br>`404` absent or not owned (**BR07**);<br>`422` page outside document |
| **PATCH** | `/documents/{document_id}/label` | JSON:<br>`user_label`, `review_state` | `200` &middot; saved user label; original AI suggestion retained | `401` unauthenticated;<br>`404` absent or not owned (**BR07**);<br>`422` invalid label (**BR03**) |
| **PATCH** | `/documents/{document_id}/folder` | JSON:<br>`folder_id` or `null` to leave unfiled | `200` &middot; updated folder; AI label unchanged | `401` unauthenticated;<br>`404` document or folder absent/not owned (**BR07**);<br>`422` invalid folder ID (**BR03**) |
| **GET** | `/folders` | — | `200` &middot; folders owned by the current user | `401` unauthenticated (**BR07**) |
| **POST** | `/folders` | JSON: `name` | `201` &middot; `folder_id`, `name` | `401` unauthenticated (**BR07**);<br>`422` blank or invalid name |
| **GET** | `/search` | Query:<br>`q`, `folder_id?`, `label?` | `200` &middot; relevance-ranked search results | `401` unauthenticated (**BR07**);<br>`422` missing query `q` |
