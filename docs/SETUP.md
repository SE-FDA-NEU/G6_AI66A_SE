# Walking Skeleton & Setup Guide

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
