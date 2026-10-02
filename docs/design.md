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

---

## 3.4 Walking skeleton

> **Route:** `GET /documents` · **Table:** `documents` (40 rows seeded across 4 users, 10 documents per user)  
> **Source Repository:** `https://github.com/Dangtooo/G6_AI66A_SE.git`

---

## 1. Prerequisites

No pre-installed software is assumed. A fresh machine requires the following tools:

- **Git:** version `2.40+` ([Download Git](https://git-scm.com/))
- **Python:** version `3.11+` or `3.12+` (with `pip` and `venv`) ([Download Python](https://www.python.org/))
- **MySQL Server:** version `8.0+` (running on default port `3306`) ([Download MySQL](https://dev.mysql.com/downloads/installer/))

---

## 2. Setup Commands (Step-by-step)

Follow the commands in sequential order. Choose the command corresponding to your operating system.

> **Quick Reference (For Experienced Developers):**
> ```bash
> git clone https://github.com/Dangtooo/G6_AI66A_SE.git
> cd G6_AI66A_SE/backend
> python -m venv .venv
> .venv\Scripts\activate       # macOS / Linux: source .venv/bin/activate
> pip install -r requirements.txt
> copy .env.example .env       # macOS / Linux: cp .env.example .env
> # STOP & EDIT: Update DB_PASSWORD in backend/.env before continuing!
> python src/init_db.py
> uvicorn app.main:app --reload
> ```

### Step-by-Step Installation

```bash
# 1. Clone the repository
git clone https://github.com/Dangtooo/G6_AI66A_SE.git
cd G6_AI66A_SE/backend

# 2. Create Python virtual environment
python -m venv .venv

# 3. Activate the virtual environment:
# On Windows (Command Prompt or PowerShell):
.venv\Scripts\activate
# On macOS / Linux:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Create local environment configuration file:
# On Windows:
copy .env.example .env
# On macOS / Linux:
cp .env.example .env
```

>  **CRITICAL: Configure `.env` before proceeding to database initialization!**  
> Do not execute database scripts yet. You **must** open `backend/.env` and update your MySQL password (`DB_PASSWORD`) in **[Section 3: Configuration (`.env`)](#3-configuration-env)** below before running the database seeding in Section 4. Otherwise, database initialization will fail with an authentication error.

---

## 3. Configuration (`.env`)

Open the newly created `backend/.env` file in your text editor and configure your local Database connection details:

>  **Prerequisite for Database Initialization:**  
> The database script (`init_db.py`) relies on these credentials to connect to your local MySQL server and create `documind_db`. If `DB_PASSWORD` is incorrect or left as default, database initialization will fail.

| Environment Variable | Sample / Default Value | Description & Instructions |
|---|---|---|
| `DB_USER` | `root` | MySQL username on your machine |
| `DB_PASSWORD` | `your_mysql_password` | **Required:** Set to your actual MySQL root password |
| `DB_HOST` | `localhost` | MySQL host address |
| `DB_PORT` | `3306` | MySQL service port |
| `DB_NAME` | `documind_db` | Database name (auto-created if not exists) |
| `SECRET_KEY` | `super_secret_key_documind_123` | Secret key used to sign and decode JWT tokens |
| `ALGORITHM` | `HS256` | JWT encryption algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | JWT token lifespan (1440 minutes = 24 hours) |

---

## 4. Database Creation & Seeding

After configuring `.env` with your valid MySQL credentials, execute database creation, table schema generation, and sample data seeding with **a single command**:

```bash
python src/init_db.py
```

### Number of Seeded Rows:
- **`users`:** **4 rows** (`demouser`, `admin`, `testuser`, `guest` — default password: `123456`).
- **`folders`:** **4 rows** (each user owns 1 dedicated folder).
- **`documents`:** **40 rows** (each user has exactly **10 documents** across PDF, DOCX, and PPTX formats).
- **`jobs`:** **20 rows** (each user has 5 processing jobs across `bullet`, `table`, and `concept` modes).
- **`job_files`:** **32 rows** (associating jobs with documents).
- **`citations`:** **12 rows** (factual evidence and citations).

### Start the Backend Server

Once the database has been successfully initialized and seeded, start the FastAPI development server:

```bash
uvicorn app.main:app --reload
```

---

## 5. How to Know It Worked (Verification Guide)

The walking skeleton route is **`GET /documents`**. Because the system enforces Business Rule **BR07** (Users can only view their own documents), this route requires a Bearer JWT token.

### Verification Steps via Swagger UI:
1. Open your browser and navigate to:  
   **`http://localhost:8000/docs`**
2. **Log in to obtain a Token:**
   - Under `Authentication`, click on **`POST /auth/login`**.
   - Click **"Try it out"**, enter `username`: `demouser`, `password`: `123456`, then click **"Execute"**.
   - Copy the `access_token` string from the response body.
3. **Authorize:**
   - Scroll to the top of the Swagger UI page, click the green **Authorize ** button.
   - Paste the token into the **Value** field and click **Authorize**, then click **Close**.
4. **Call `GET /documents`:**
   - Under `Documents`, click on **`GET /documents`**.
   - Click **"Try it out"** > click **"Execute"**.

### Expected Response:
The server returns HTTP Status **`200 OK`** with exactly **10 documents** belonging to `demouser` (with `extracted_text` deferred to optimize payload):

```json
[
  {
    "id": 1,
    "owner_id": 1,
    "folder_id": 1,
    "original_filename": "hop_dong_lao_dong.pdf",
    "storage_path": "/storage/demouser/hop_dong_lao_dong.pdf",
    "file_format": "PDF",
    "file_size_bytes": 1048576,
    "page_count": 6,
    "ai_label": "Hợp đồng",
    "ai_confidence": 0.95,
    "review_state": "confirmed",
    "user_label": "Hợp đồng nhân sự",
    "last_accessed_at": "2026-09-30T14:00:00",
    "expires_at": "2026-10-30T14:00:00",
    "created_at": "2026-09-30T14:00:00"
  },
  {
    "id": 2,
    "owner_id": 1,
    "folder_id": 1,
    "original_filename": "bao_cao_tai_chinh_q3.docx",
    "storage_path": "/storage/demouser/bao_cao_tai_chinh_q3.docx",
    "file_format": "DOCX",
    "file_size_bytes": 2097152,
    "page_count": 12,
    "ai_label": "Tài chính",
    "ai_confidence": 0.88,
    "review_state": "confirmed",
    "user_label": "Báo cáo Q3",
    "last_accessed_at": "2026-09-30T14:00:00",
    "expires_at": "2026-10-30T14:00:00",
    "created_at": "2026-09-30T14:00:00"
  }
]
```

*(Or quickly test using a single cURL command)*:
```bash
curl -X GET "http://localhost:8000/documents?skip=0&limit=50" -H "Authorization: Bearer <TOKEN_FROM_LOGIN>"
```

### Screenshot of the Running Page:
The screenshot below demonstrates the running API endpoint on Swagger UI (`http://127.0.0.1:8000/documents?skip=0&limit=50`) returning HTTP `200 OK` with the seeded documents:

![Screenshot of the Running Page - Swagger UI Response](images/response_body.png)

---

## 6. The Query Behind the Page (Query in `design.md`)

When a user calls `GET /documents`, SQLAlchemy generates the following equivalent SQL query (filtering by the authenticated user's `owner_id` and excluding `extracted_text` via `defer`):

```sql
SELECT 
    documents.id,
    documents.owner_id,
    documents.folder_id,
    documents.original_filename,
    documents.storage_path,
    documents.file_format,
    documents.file_size_bytes,
    documents.page_count,
    documents.ai_label,
    documents.ai_confidence,
    documents.review_state,
    documents.user_label,
    documents.last_accessed_at,
    documents.expires_at,
    documents.created_at
FROM documents 
WHERE documents.owner_id = 1
ORDER BY documents.created_at DESC
LIMIT 50 OFFSET 0;
```

### Screenshot of SQL Query and Fetched Data:
The screenshot below shows the executed query in the database client and the resulting records returned from the `documents` table:

![Screenshot of SQL Query and Fetched Data](images/sql_query.png)

---

## 7. Troubleshooting (Common Issues on Fresh Machines)

### Issue 1: `sqlalchemy.exc.OperationalError: Can't connect to MySQL server on 'localhost' ([WinError 10061])`
- **Cause:** The MySQL service is not running or the `DB_PASSWORD` in `.env` is incorrect.
- **Resolution:**
  - On Windows: Run PowerShell as Admin and execute `net start MySQL80` (or open `services.msc` > Start `MySQL80` service).
  - On macOS/Linux: Run `sudo systemctl start mysql` (or `brew services start mysql`).
  - Open `.env` and verify your `DB_PASSWORD`.

### Issue 2: `HTTP 401 Unauthorized` (`{"detail": "Not authenticated"}`)
- **Cause:** Called `GET /documents` without providing the `Authorization: Bearer <token>` header.
- **Resolution:**
  - Call `POST /auth/login` with `demouser` / `123456` to get a token.
  - On Swagger UI: Click the **Authorize ** button and paste the token.

### Issue 3: `ModuleNotFoundError: No module named 'app'`
- **Cause:** You are running commands from the `backend/app/` subdirectory instead of the `backend/` root directory.
- **Resolution:**
  - Run `cd ..` to return to the `backend/` directory, then re-run `uvicorn app.main:app --reload`.

---

## 8. Tested By (Independent Verification Log)

- **Tester:** `@hoang3003` (Team 3)
- **Environment:** Fresh Windows 11 Laptop (fresh clone)
- **Execution Time:** 2026-10-1 — **6 minutes**
- **Result:** Successfully executed all steps from clone to running the server and testing `GET /documents` on Swagger UI with 100% pass rate, returning exactly 10 documents for user `demouser`.

---

## 3.5 Architecture Decision Records

### Decision 1 - MySQL 8.x instead of SQLite or PostgreSQL

* **Options**: SQLite file · PostgreSQL in Docker · MySQL 8.x.
* **Chose**: MySQL 8.x.
* **Why**: SQLite's database-level lock would cause errors during concurrent writes from our background AI workers. PostgreSQL adds Docker complexity to the local setup and uses too much RAM for an AWS Free Tier server. MySQL provides the necessary row-level locking natively without the overhead.
* **What would change our mind**: If our app required complex JSONB analytics or geospatial queries that MySQL couldn't handle efficiently, we would move to PostgreSQL.

### Decision 2 — Tracking status in both ```jobs``` and ```job_files```

* **Options**: Status in ```jobs``` only · Status in ```job_files``` only · Status in both.
* **Chose**: Status in both.
* **Why**: Our batch processing allows up to 5 files per job. Tracking status globally in jobs is needed for the overall UI progress bar, but tracking in ```job_files``` is strictly required to identify exactly which specific file failed and why.
* **What would change our mind**: If we disabled batch processing and restricted users to strictly one file per upload, ```job_files``` would become redundant and we would merge the status into the ```documents``` table.