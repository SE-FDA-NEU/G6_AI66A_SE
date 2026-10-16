# Walking Skeleton & Setup Guide

> **Route:** `GET /documents` · **Table:** `documents` (40 rows seeded across 4 users, 10 documents per user)  
> **Source Repository:** `https://github.com/Dangtooo/G6_AI66A_SE.git`

---

## 1. Prerequisites

No pre-installed software is assumed. A fresh machine requires the following tools:

- **Git:** version `2.40+` ([Download Git](https://git-scm.com/))
- **Python:** version `3.11+` or `3.12+` (with `pip` and `venv`) ([Download Python](https://www.python.org/))
- **MySQL Server:** version `8.0+` (running on default port `3306`) ([Download MySQL](https://dev.mysql.com/downloads/installer/))
- **Node.js:** version `20.9+` with npm, required for the Next.js frontend and Playwright tests.

Sections 2–7 describe the standalone backend. To run the Next.js landing page with FastAPI, follow [Section 8](#8-nextjs-landing-page-and-sign-in-task-62): Next.js uses port **8000**, and FastAPI uses port **8001**.

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

## 8. Next.js Landing Page and Sign-in (Task #62)

The `/` page shows the DocuMind introduction and an email/password sign-in form. It calls `POST /auth/login`; FastAPI validates the account and sets a JWT in the `documind_session` HttpOnly cookie. A successful sign-in redirects to `/workspace`. Failed sign-in shows an inline error. The workspace currently provides a minimal sign-in destination and logout; document management belongs to #63.

Next.js serves the UI on **8000** and forwards `/auth/*` to FastAPI on **8001** using `frontend/next.config.mjs`. Both servers must be running to sign in manually. `BACKEND_ORIGIN` can override the backend address.

### Install dependencies (Windows PowerShell)

From the repository root, create the Python environment if it does not already exist:

```powershell
python -m venv backend/.venv
& backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..
```

For manual sign-in, configure `backend/.env` following Section 3, including your MySQL password and a private `SECRET_KEY`. MySQL must be running. If this is a fresh database, initialize it following Section 4. Existing accounts can sign in using the email stored in `users.email`; API clients can still use their username.

### Terminal 1 — start FastAPI

From the repository root:

```powershell
cd backend
& .venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

If you need a development account, run the following from `backend` before starting the server:

```powershell
& .venv/Scripts/python.exe test/create_test_user.py
```

This script adds missing development users without dropping tables. You can then sign in with `test@gmail.com` and password `123456`. These credentials are for local development only.

### Terminal 2 — start Next.js

From the repository root:

```powershell
cd frontend
npm run dev
```

Open **http://127.0.0.1:8000**. FastAPI Swagger is at **http://127.0.0.1:8001/docs**. If the standalone backend from Section 4 is still using port 8000, stop it and restart it on 8001 before starting Next.js.

On macOS/Linux, use `.venv/bin/python` instead of `.venv/Scripts/python.exe`; omit PowerShell's `&` prefix.

### Run Playwright tests

After installing the Python and frontend dependencies above, run from the repository root:

```powershell
cd frontend
npx playwright install chromium
npx playwright test tests/auth.spec.js
```

No manual `npm run dev` or Uvicorn command is needed for tests. Playwright automatically starts Next.js on **18000** and FastAPI on **18001**, then stops them after the tests. Those two ports must be free.

The test backend uses the real authentication endpoints with a disposable in-memory SQLite database and a test signing key. It does not connect to or modify your MySQL database, and does not require your local MySQL credentials. The launcher uses `backend/.venv` when available, otherwise `python` from PATH. Set `E2E_PYTHON` if you need a different Python executable.

The seven tests cover invalid credentials and retry, HttpOnly cookies, session persistence, logout, guest/forged-session redirects, network errors, email validation, mobile layout and legacy username API clients. They verify task #62 authentication behavior; MySQL integration and the full document workspace require separate validation.

### Next.js route guard

`frontend/proxy.js` runs before requests to `/workspace`, `/upload`, `/results/*` and `/documents/*` (including their root paths). Next.js 16 renamed the `middleware.js` convention to `proxy.js`; this file implements the route guard middleware for the installed version.

The guard redirects missing or invalid sessions to `/` with HTTP 307. It validates the HttpOnly cookie through FastAPI `/auth/me`, which checks the JWT signature, expiration and account existence. If validation cannot reach the backend, access is denied. The existing workspace server-side validation remains in place. The landing page, authentication endpoints and frontend assets are outside the guard matcher.

Run the guard tests from `frontend`:

```powershell
npx playwright test tests/route-guard.spec.js
# Run all authentication, route-guard and document-access tests:
npx playwright test
```

The tests cover a fresh browser session, missing tokens, signed expired tokens whose cookies are still present, forged signatures, valid sessions and public routes. The workspace and upload selection page return HTTP 200 for valid sessions. Results/document pages are not implemented yet; valid sessions pass the guard and receive their current 404 response.

For manual verification, start both servers as above, open a private/incognito browser window, and visit `http://127.0.0.1:8000/workspace`. It should return to `/` and display the sign-in form. Repeat with `/upload`, `/results/1` and `/documents/1`.

### Guest redirects and cross-account access (task #64)

From `frontend`, run:

```powershell
npx playwright test tests/route-guard.spec.js tests/document-access.spec.js
```

The route-guard suite verifies unauthenticated `GET /workspace` returns HTTP 307 to `/` and a fresh browser reaches the sign-in form. The document-access suite calls FastAPI directly on port **18001** using real login-issued Bearer tokens with cookies suppressed. Two test users each own a private document: the owner receives HTTP 200, the other account receives HTTP 403 with only `{"detail":"Access denied"}`, and denied access leaves retention timestamps unchanged. It also verifies list isolation, guest HTTP 401 and missing-document HTTP 404. This updates the document-detail contract from the earlier combined HTTP 404 behavior to the explicit HTTP 403 required by #64.

Fixtures are disposable SQLite data; no real files or MySQL data are used. The `Auth and document access tests` CI job installs both stacks and Chromium, runs the complete Playwright suite and uploads failure traces.

On Linux CI, install browser system dependencies with `npx playwright install --with-deps chromium`.

### Check the production build

From `frontend`:

```powershell
npm run build
npm start
```

Keep FastAPI running on 8001 when using `npm start`. Stop `npm run dev` first because both frontend commands use port 8000.

### Troubleshooting task #62

- **`Cannot find package '@playwright/test'`:** run `npm ci` inside `frontend`.
- **`Invalid URL` in Playwright:** run the test inside `frontend` so it loads `playwright.config.js` and its `baseURL`.
- **`Executable doesn't exist`:** run `npx playwright install chromium` inside `frontend`.
- **Connection or server error during manual sign-in:** check that FastAPI is running on 8001, MySQL is running, and `backend/.env` is configured correctly.
- **`Address already in use`:** stop the process using the relevant port; tests use 18000/18001 and manual development uses 8000/8001.

---

## 9. Tested By (Independent Verification Log)

- **Tester:** `@hoang3003` (Team 3)
- **Environment:** Fresh Windows 11 Laptop (fresh clone)
- **Execution Time:** 2026-10-1 — **6 minutes**
- **Result:** Successfully executed all steps from clone to running the server and testing `GET /documents` on Swagger UI with 100% pass rate, returning exactly 10 documents for user `demouser`.

### Client-side upload validation (task #65)

Sign in, click **Tải tài liệu** in the workspace, or open `http://127.0.0.1:8000/upload`. Select or drop PDF, DOCX or PPTX files. Limits are inclusive: five files, 5 MB per file and 50 MB total (1 MB = 1,048,576 bytes). Rejected files stay visible with individual error badges but do not count as valid selections. Existing valid files remain selected when more files are added. Remove files with **Xóa**; validation runs again, so a previously rejected sixth file becomes valid when a slot opens. File selection performs no upload requests. Actual transfer and processing are not part of #65.

From `frontend`:

```bash
npx playwright test tests/upload-validation.spec.js
```

Tests cover format checks (including misleading MIME types), exact byte limits, the independent 50 MB batch guard, five 5 MB files, a rejected sixth file, retained selections, removal/revalidation, drag/drop and mobile layout. The existing CI Playwright job includes this suite automatically.
### Server-side upload validation (task #66)

Install test dependencies and run the isolated API suite from the repository root:

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
backend/.venv/bin/python -m pytest backend/tests -v
```

On Windows use `backend/.venv/Scripts/python.exe`. Tests use a dedicated signing key, an isolated in-memory SQLite database and temporary storage. They do not access MySQL or require running servers; temporary uploaded files are removed after each test.

For manual testing, run FastAPI on port 8001, open `http://127.0.0.1:8001/docs`, authenticate via `/auth/login`, then call `POST /upload` with multipart `files` and optional `mode` (`bullet`, `table`, `concept`; default `bullet`). Valid batches now return HTTP **202** with `{"jobId":"123"}` after saving files and committing a pending job. Invalid batches return HTTP 422 with `detail.batch_errors` and `detail.files`, including zero-based indexes and error codes. Limits remain five PDF/DOCX/PPTX files, at most 5 MB each and 50 MB combined (1 MB = 1,048,576 bytes). See `docs/design.md` for the response contract.

### Async upload, storage and job creation

No database migration or additional runtime package is needed: the endpoint uses the existing Document, Job and JobFile models. Files are stored by default under `backend/data/uploads/<owner>/<random-batch>/` using random filenames. Set `STORAGE_DIR` in `backend/.env` to change the upload root. Uploaded data is excluded from Git.

Example from PowerShell after obtaining a token:

```powershell
curl.exe -X POST "http://127.0.0.1:8001/upload" -H "Authorization: Bearer YOUR_TOKEN" -F "files=@C:\path\report.pdf" -F "mode=bullet"
curl.exe "http://127.0.0.1:8001/jobs/123" -H "Authorization: Bearer YOUR_TOKEN"
```

The response is sent without waiting for processing. Background work runs through `asyncio.create_task`, with blocking worker work offloaded to a thread and its own database session. Storage or database failure rolls back the new batch and cleans up its files; queue submission failure returns 503 and records a failed job. The queue drains outstanding tasks on graceful shutdown, but tasks are not durable across process crashes.

**Current worker scope:** AI/document processing belongs to the later worker task. The entry point `backend/app/services/processing.py` currently records a clear failed job/file error: `Document processing worker is not integrated yet.` A 202 response means the upload was accepted and enqueued, not that analysis succeeded. Saved source files remain available for the later processing integration. The frontend selection page still does not submit files automatically.

Run the complete backend suite from the repository root:

```powershell
& backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
& backend/.venv/Scripts/python.exe -m pytest backend/tests -q
```

`test_upload_jobs.py` verifies saved bytes, transaction rollback, safe storage paths, job/file ownership, modes, enqueue/worker failures and the response arriving while a real background worker is blocked. Existing #66 validation tests remain included.
