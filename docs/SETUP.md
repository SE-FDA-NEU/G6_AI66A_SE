# Run DocuMind locally and in production

DocuMind uses Next.js on port **8000**, FastAPI on port **8001** and MySQL on port **3306**. Run commands from the repository root unless a step says otherwise. Sections 1–6 cover local startup; section 7 preserves isolated test instructions; section 8 covers production.

## 1. Prerequisites

| Tool | Required version / purpose |
|---|---|
| Git | Clone the repository. |
| Python | 3.11 or newer, with pip and venv. |
| Node.js and npm | Node.js 20.9 or newer. |
| MySQL Server | 8.0 or newer; start the local MySQL service. |
| Gemini API key | Enter a personal key in the signed-in upload form for AI analysis; the app stores it encrypted to that account. An optional server key supports semantic search/internal tools. |

PDF, DOCX and PPTX reading uses the Python packages in `backend/requirements.txt`. **LibreOffice and `SOFFICE_BINARY` are not required by the current code.** DOCX is displayed as generated text-reader pages; PPTX uses one generated page per slide. Original Office formatting is not reproduced exactly.

## 2. Clone and configure

```powershell
git clone https://github.com/SE-FDA-NEU/G6_AI66A_SE.git
cd G6_AI66A_SE
Copy-Item backend/.env.example backend/.env
```

If you already have the project and `backend/.env`, keep that file and edit its values instead of copying over it.

Open `backend/.env` and set:

```dotenv
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=documind_db

SECRET_KEY=replace_with_a_random_secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

Generate a value for `SECRET_KEY`, then paste it into the file:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Keep the remaining defaults from `.env.example`. `GEMINI_MODEL` must identify a model available to your key. Sign in and enter your personal key in the upload form before analysis; a server `GEMINI_API_KEY` alone does not satisfy the current upload API’s account-key requirement. Sign-in, source reading and keyword search remain available without AI credentials. Semantic search uses the optional server provider key. Keep `SECRET_KEY` stable so saved personal keys can still be decrypted.

Use a database dedicated to DocuMind. The launcher creates missing tables. Keep `DB_DROP_EXTRA_TABLES=false` on shared/cloud databases; removing extra tables requires explicitly enabling the destructive option and first making a backup under `backend/data/backups/`. Existing columns are not migrated automatically. The MySQL account needs the corresponding database/schema permissions. Do not commit `.env` or database backups.

## 3. First-time preparation

Make sure MySQL is running, then execute:

```powershell
python run.py --setup-only
```

This creates `backend/.venv`, installs backend dependencies, runs `npm ci` when the frontend is not installed, and prepares the database. It does not create a login account or run tests.

To create your own account, start the application, open the landing page and select **Sign up / Đăng ký** below the sign-in form. Enter a unique username (3–100 ASCII letters, numbers, dots, underscores or hyphens), email, password and matching confirmation. Passwords require at least 8 characters and at most 72 UTF-8 bytes. Registration signs you into a new private workspace; no database migration or demo seed is needed beyond the existing schema preparation. You can also create an account through `POST /auth/register` with JSON fields `username`, `email` and `password`; success returns 201 with the existing token response and HttpOnly session cookie. Duplicate identities return 409 and invalid input returns 422.

Create the local demo account and its 20 synthetic PDF documents:

```powershell
& ./backend/.venv/Scripts/python.exe backend/src/init_db.py --acceptance
```

| Sign-in field | Value |
|---|---|
| Email | `acceptance145@example.invalid` |
| Password | `Acceptance145!Local` |

This seed provides readable sample files for the workspace. Upload files and choose an analysis mode to create a new AI result. Sample sources are in `backend/test/fixtures/acceptance/`; the `test` directory name does not mean the seed command runs tests.

## 4. Start the application

```powershell
python run.py
```

The launcher starts both servers and opens the browser. On later runs, this is the only startup command needed. To keep the browser closed automatically, use `python run.py --no-browser`.

| Service | Address |
|---|---|
| Web application | http://127.0.0.1:8000 |
| FastAPI / Swagger | http://127.0.0.1:8001/docs |

Sign in, open **Upload documents**, select 1-5 supported files of at most 5 MB each, choose Table/Bullet/Concept, and start processing. Results open automatically. Select a source citation to inspect the document in Reader. Stop both servers with **Ctrl+C** in the launcher terminal.

## 5. Run the servers separately (optional)

Use this after completing configuration and database preparation above. Stop `run.py` before using these commands.

Terminal 1 - backend:

```powershell
cd backend
& ./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Terminal 2 - frontend, starting from the repository root:

```powershell
cd frontend
npm run dev
```

In development, Next.js forwards API requests to `http://127.0.0.1:8001` by default. Set `BACKEND_ORIGIN` in the frontend process if the backend address changes. Both servers must run for sign-in and document operations. Production requires an explicit non-loopback `BACKEND_ORIGIN` at both build and runtime.

### Production frontend (Render / #253)

See [the Render deployment guide](deploy-frontend-render.md) and the frontend-only
`render.yaml` blueprint. Use a Node Web Service with root directory `frontend`,
build command `npm ci && npm run build`, and start command `npm start`.
Set `NODE_VERSION=24`, `NODE_ENV=production` and the confirmed HTTPS
`BACKEND_ORIGIN`. The start command binds `0.0.0.0` and reads the host's `PORT`.
Rebuild after changing the backend origin: start refuses origins inconsistent
with the compiled rewrites. Never use a Static Site for this SSR application.

For a local production build against an approved backend (PowerShell):

```powershell
cd frontend
$env:BACKEND_ORIGIN = 'https://<backend-host>'
$env:PORT = '8000'
npm.cmd ci
npm.cmd run build
npm.cmd start
```

Keep the same origin in the build and running process. The currently supplied
backend health URL is `https://documind-n9ny.onrender.com/health`; confirm the
release SHA with its owner. Browser API calls stay on the frontend origin,
and sessions remain HttpOnly cookies. No CORS change is needed for this flow.

For macOS/Linux, replace `Copy-Item` with `cp`, use `python3` if needed, and run the seed/backend with `backend/.venv/bin/python` or `.venv/bin/python` instead of the Windows executable.

## 6. Troubleshooting

| Problem | Action |
|---|---|
| Cannot connect to MySQL | Start the MySQL service and check `DB_HOST`, `DB_PORT`, `DB_USER` and `DB_PASSWORD` in `backend/.env`. |
| Schema preparation fails | Use a dedicated database and an account with database/table permissions. Read the terminal error and backup location before retrying. |
| Sign-in fails on a fresh database | Run the acceptance seed, then use the email/password above. Existing accounts retain their stored credentials. |
| PowerShell blocks `npm.ps1` | Use `npm.cmd ci` or `npm.cmd run dev`. Venv activation is unnecessary when using the Python executable directly. |
| Port 8000 or 8001 is occupied | Stop the old launcher/server before starting another instance. |
| AI is not configured / provider rejects a request | Enter or replace the account’s personal Gemini key in the upload form; the backend model must be available to that key. Server `GEMINI_API_KEY` is separate. |
| Old `converter_unavailable` / LibreOffice error | Stop old server processes, install the current `backend/requirements.txt` in `backend/.venv`, restart from this checkout and submit again. Current Office reading uses Python libraries. |
| Reader source is missing | Upload the original file again. Older metadata-only demo rows do not provide real source files. |
| Dependencies need reinstalling | Run `& ./backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt`, then run `npm.cmd ci` inside `frontend`. |

## 7. Run isolated tests

### Backend (pytest)

These steps need Python 3.11+ only; skip the application configuration, database preparation and demo seed above. From the repository root, create a virtual environment if one does not exist:

```powershell
python -m venv backend/.venv
cd backend
& ./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
& ./.venv/Scripts/python.exe -m pytest tests -v
```

`requirements-dev.txt` includes the runtime dependencies and test tools. The required pytest `tests/` directory is **`backend/tests/`**, run from **`backend/`**. `conftest.py` supplies in-memory SQLite, temporary upload storage, authenticated TestClient requests and a recording queue; processing tests use controlled processors/providers. No real credentials, MySQL, Gemini calls or separately running servers are required. Acceptance data lives in `backend/test/fixtures/acceptance/`; it is separate from the pytest suite.

To run only the processing lifecycle checks, from `backend/`:

```powershell
& ./.venv/Scripts/python.exe -m pytest tests/test_job_lifecycle.py tests/test_processing_timeouts.py tests/test_upload_jobs.py -v
```

### Frontend (Playwright)

Install the Python development dependencies above, then run these commands from the repository root:

```powershell
cd frontend
npm.cmd ci
npx.cmd playwright install chromium webkit
npm.cmd test
```

Playwright starts its own isolated API fixture server on **18001** and Next.js on **18000**; keep these ports free. It uses temporary SQLite/storage and seeded test data rather than the application database. The launcher selects `backend/.venv` automatically; set `E2E_PYTHON` to an absolute Python executable path only when using another environment with the development dependencies installed. Do not start `run.py` for these tests.

For the lifecycle UI checks only, run `npm.cmd test -- tests/job-lifecycle.spec.js --project=chromium` from `frontend/`. On Linux, install browser system dependencies with `npx playwright install --with-deps chromium webkit`. On macOS/Linux, use `.venv/bin/python` in `backend/` and `npm`/`npx` instead of the Windows commands above.


## 8. Production: Render + cloud MySQL

### Public entry and local/production distinction

| Surface | Address / purpose |
|---|---|
| Public application | https://documind-web-k6i1.onrender.com |
| Public readiness | https://documind-web-k6i1.onrender.com/health |
| Backend origin | https://documind-n9ny.onrender.com |
| Backend readiness | https://documind-n9ny.onrender.com/health |
| Local application / API | http://127.0.0.1:8000 / http://127.0.0.1:8001; use sections 1–6 |

Run `python run.py` locally only. Production uses two Render **Web Services**:
Next.js requires SSR, HttpOnly session lookup and external rewrites, so do not
use a static export or Static Site. FastAPI runs without reload. The backend
needs hosted MySQL-compatible TiDB, a persistent writable filesystem, writable
temporary space and extraction subprocess support. PostgreSQL/SQLite substitutions
would change the existing schema/runtime contract; they are not part of this setup.

### Backend environment and startup

Set values in Render environment/secret settings (and GitHub Secrets only where
a CI/deploy job needs them). Values below are placeholders, never real secrets.
Use provider-supplied connection details and a dedicated application database.

```dotenv
DB_HOST=<cloud-mysql-host>
DB_PORT=<cloud-mysql-port>
DB_NAME=<dedicated-database>
DB_USER=<application-user>
DB_PASSWORD=<database-password>
DB_SSL_MODE=verify_identity
DB_SSL_CA=<absolute-path-to-provider-ca.pem>
DB_DROP_EXTRA_TABLES=false
DB_CONNECT_TIMEOUT_SECONDS=10
DB_READ_TIMEOUT_SECONDS=30
DB_WRITE_TIMEOUT_SECONDS=30
DB_POOL_PRE_PING=true
DB_POOL_RECYCLE_SECONDS=1800
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT_SECONDS=30
STORAGE_DIR=/var/data/documind/uploads
BACKUP_DIR=/var/data/documind/backups
SECRET_KEY=<stable-generated-random-secret>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ANALYSIS_PROVIDER=gemini
GROQ_FALLBACK_ENABLED=false
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_API_KEY=<optional-server-key-for-semantic-search>
JOB_SHUTDOWN_GRACE_SECONDS=10
JOB_SHUTDOWN_CLEANUP_SECONDS=8
RETENTION_CLEANUP_ENABLED=true
RETENTION_CLEANUP_INTERVAL_SECONDS=3600
RETENTION_CLEANUP_BATCH_SIZE=100
```

Use the CA file supplied by the database provider; configure its trusted system
CA instead if the provider uses a publicly trusted chain. Never disable identity
verification to mask a certificate error. PyMySQL connects using `utf8mb4`.
Choose application permissions needed for queries; perform schema preparation
with a separately authorized maintenance account. Keep schema changes and
backups separate from API startup; existing columns require reviewed migrations.

Render backend root directory: `backend`. Build command:

```bash
python -m pip install -r requirements.txt
```

Prepare/verify the dedicated schema as a maintenance step using the configured
DB environment: `python -m app.db.bootstrap`. Back up existing DB/files before
schema changes; keep `DB_DROP_EXTRA_TABLES=false`. Coordinate source seeding and
path validation with the data owner; do not run local fixture seeding against
an existing production database blindly.

Start command (one instance and one worker):

```bash
uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1 --no-access-log --log-config logging.json
```

Render supplies `PORT`. Configure Uvicorn’s `--proxy-headers` and
`--forwarded-allow-ips <trusted-edge-addresses>` using verified platform proxy
addresses; never trust arbitrary forwarded HTTPS headers. The TLS edge must
replace client-supplied forwarded headers. Verify Secure/HttpOnly/SameSite=Lax
cookies through the frontend URL. See [proxy/session verification](deploy-frontend-render.md).

Mount storage at the actual persistent-disk path before setting `STORAGE_DIR`.
Store originals, `.reader` PDFs and analysis caches together; a writable ephemeral
container path is insufficient. Backups also need encrypted off-host copies;
a backup on the same disk alone is not disaster recovery. See
[operations](operations.md) for backup/restore, retention and monitoring.
Stop the old backend process tree before replacement; do not run overlapping
workers. Allow more than the combined 18-second default queue shutdown budgets
plus database/scheduler cleanup. Startup fails interrupted work visibly rather
than resuming it automatically. See [restart handling](processing-restart.md).

### Frontend environment and startup

Render frontend root directory: `frontend`. Use the committed [Blueprint](../render.yaml)
or the [frontend deployment guide](deploy-frontend-render.md).

```dotenv
NODE_ENV=production
NODE_VERSION=24
BACKEND_ORIGIN=https://<backend-service>.onrender.com
```

```bash
npm ci && npm run build
npm start
```

`npm start` binds `0.0.0.0` and uses platform `PORT`. `BACKEND_ORIGIN` is
server-only and must be present at **build and runtime**, with identical values.
Use the backend origin, without path/query/credentials; never localhost or the
frontend origin. A change requires a rebuild because API rewrites are compiled
into the build. Production rejects missing/local origins and runtime/build drift.
The browser uses same-origin `/auth`, `/jobs`, `/api/upload`, `/api/search`,
`/api/folders`, `/api/documents` and `/health` proxies; no browser-visible key or
cross-origin workaround is needed. Keep credentialed CORS disabled unless an
explicit allowed-origin flow requires it.

The Next proxy allowance is 30 MiB for five 5 MiB files plus multipart overhead;
also check host/edge request limits. Polling follows the upload’s 202/job ID.
Backend processing occurs outside that HTTP request.

### Secrets, readiness and checks

Personal Gemini keys are entered in the account upload UI and encrypted by the
backend. Keep the JWT/encryption `SECRET_KEY` stable across deploys and restores;
changing it invalidates sessions and makes saved keys unreadable. Keep optional
server provider keys in platform secrets, never `NEXT_PUBLIC_*`, README, Git or
logs. A committed real key must be revoked and replaced.

Set the platform health path to `/health`: API plus bounded DB query returns
200 with `status=ok,database=ready`; unavailable DB returns 503 without secrets.
AI availability is checked separately by a real analysis job. Preserve no-store
responses. Configure deploy-after-green for the main branch and review through
PRs. Do not replace section 7’s isolated checks with production calls.

From the public landing, test demo login/logout, F5 session/data persistence,
large uploads, Table/Bullet/Concept, ≥20-document search, source citations and
cross-account denial. Read logs on each Render service and verify storage after
restart. The [release record](release-acceptance.md) contains observed results;
[CI evidence](ci-release-checks.md) and [operations](operations.md) describe release
and recovery. Live Render settings must be checked against this configuration;
the frontend-only Blueprint does not configure the separately managed backend.
