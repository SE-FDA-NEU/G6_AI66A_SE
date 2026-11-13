# Task #255 — clean-clone documentation verification

Verified 13 November 2026. A separate clean clone of candidate `22c348db6d115ef6a3d64a4d3bdf61983840c1a5` was
created with `git clone --no-hardlinks`, without copying environment files,
uploads, databases or frontend build artifacts. A fresh `backend/.venv` was
created and dependencies installed from `requirements-dev.txt`; frontend used
`npm ci`. The cloned working tree is clean. Environment: Python 3.12.6,
Node 25.9.0 on macOS; CI separately specifies Node 24/Python 3.12.

| Command / check | Actual result | Raw output |
|---|---|---|
| `python -m pip install -r requirements-dev.txt` | Passed in the fresh venv | Dependency installation completed; no application credentials used |
| `npm ci` | Passed | Lockfile installation succeeded |
| `npm run test:config` | 3 passed | [Config](setup-255/frontend-config.txt) |
| `BACKEND_ORIGIN=https://documind-n9ny.onrender.com npm run build` | Passed, production SSR pages generated | [Build](setup-255/frontend-build.txt) |
| `python -m pytest tests/test_local_launcher.py tests/test_database_bootstrap.py tests/test_health.py -q` | 8 passed, 5 skipped | [Launcher/health/bootstrap](setup-255/backend-launcher-health-bootstrap.txt) |
| `python -m pytest tests/test_cloud_mysql_schema.py -q` | 9 passed | [Cloud schema/config](setup-255/backend-cloud-schema.txt) |
| Existing SETUP section 7 | Preserved byte-for-byte before appending production section 8 | Checked against the preceding committed document |

The five skips are explicit opt-in real-MySQL bootstrap cases requiring
`DOCUMIND_MYSQL_TESTS=1` and a disposable DB environment. The nine cloud-schema
checks use controlled DB/configuration fixtures; this is not a new live TiDB
migration or proof of platform settings. The complete pytest/Playwright suites
were not rerun for these documentation-only changes. Live app/AI/source checks
remain in the existing [acceptance record](live-acceptance-257.md).

README now starts with the public HTTPS URL and main badge, lists the verified
ordinary demo account and P0 starting clicks, and records Dương as Sprint 5 SM.
SETUP distinguishes local launcher from production commands; documents DB/TLS,
persistent STORAGE_DIR/BACKUP_DIR, stable JWT/encryption secret, personal versus
server AI keys, build/runtime BACKEND_ORIGIN, trusted proxy headers, 30 MiB proxy
allowance, one worker, health and restart limits. Configuration uses placeholders.
The public search-entry fix remains documented as awaiting deployment in PR #271.
