# Run DocuMind locally

DocuMind uses Next.js on port **8000**, FastAPI on port **8001** and MySQL on port **3306**. Run commands from the repository root unless a step says otherwise. No test commands are required for this setup.

## 1. Prerequisites

| Tool | Required version / purpose |
|---|---|
| Git | Clone the repository. |
| Python | 3.11 or newer, with pip and venv. |
| Node.js and npm | Node.js 20.9 or newer. |
| MySQL Server | 8.0 or newer; start the local MySQL service. |
| Gemini API key | Required to generate AI labels, summaries, comparisons and concepts; keep it in the backend environment. |

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

Keep the remaining defaults from `.env.example`. `GEMINI_MODEL` must identify a model available to your key. Without a key, sign-in, file reading and keyword search remain available, but analysis reports that AI is not configured. Semantic search also requires provider access.

Use a database dedicated to DocuMind. The launcher creates missing tables and removes tables outside the application's six-table schema after making a backup under `backend/data/backups/`. Existing columns are not migrated automatically. The MySQL account needs the corresponding database/schema permissions. Do not commit `.env` or database backups.

## 3. First-time preparation

Make sure MySQL is running, then execute:

```powershell
python run.py --setup-only
```

This creates `backend/.venv`, installs backend dependencies, runs `npm ci` when the frontend is not installed, and prepares the database. It does not create a login account or run tests.

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

Next.js forwards API requests to `http://127.0.0.1:8001` by default. Set `BACKEND_ORIGIN` in the frontend process only if the backend address changes. Both servers must run for sign-in and document operations.

For macOS/Linux, replace `Copy-Item` with `cp`, use `python3` if needed, and run the seed/backend with `backend/.venv/bin/python` or `.venv/bin/python` instead of the Windows executable.

## 6. Troubleshooting

| Problem | Action |
|---|---|
| Cannot connect to MySQL | Start the MySQL service and check `DB_HOST`, `DB_PORT`, `DB_USER` and `DB_PASSWORD` in `backend/.env`. |
| Schema preparation fails | Use a dedicated database and an account with database/table permissions. Read the terminal error and backup location before retrying. |
| Sign-in fails on a fresh database | Run the acceptance seed, then use the email/password above. Existing accounts retain their stored credentials. |
| PowerShell blocks `npm.ps1` | Use `npm.cmd ci` or `npm.cmd run dev`. Venv activation is unnecessary when using the Python executable directly. |
| Port 8000 or 8001 is occupied | Stop the old launcher/server before starting another instance. |
| AI is not configured / provider rejects a request | Set a valid backend `GEMINI_API_KEY` and accessible `GEMINI_MODEL`, then restart the backend and submit a new job. |
| Old `converter_unavailable` / LibreOffice error | Stop old server processes, install the current `backend/requirements.txt` in `backend/.venv`, restart from this checkout and submit again. Current Office reading uses Python libraries. |
| Reader source is missing | Upload the original file again. Older metadata-only demo rows do not provide real source files. |
| Dependencies need reinstalling | Run `& ./backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt`, then run `npm.cmd ci` inside `frontend`. |
