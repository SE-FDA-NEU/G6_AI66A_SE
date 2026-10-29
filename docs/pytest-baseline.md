# Pytest Baseline and Isolated Environment Verification

This document records the verification of the isolated pytest environment, baseline test suite results, acceptance fixture tracking, baseline failure resolution, and the standardized test-case evidence format for Sprint 4 (#205).

---

## 1. Isolated Environment Verification

The backend test suite in `backend/tests/` executes in complete isolation without requiring a running backend server, a real MySQL database, external AI API access, or developer credentials in `.env`.

### Isolation Mechanisms in `backend/tests/conftest.py`

1. **In-Memory SQLite Database**:
   - Configured via `create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)`.
   - Enforces foreign key constraints via SQLite event listener (`PRAGMA foreign_keys=ON`).
   - Automatically bootstraps schema using `Base.metadata.create_all(engine)` and seeds initial test users (`upload_user`, `other_user`).
2. **Ephemeral File Storage**:
   - `STORAGE_DIR` is monkeypatched to `tmp_path / 'uploads'`, ensuring all uploaded files are isolated and automatically cleaned up after test completion.
3. **Mocked Job Queue & Pipeline**:
   - `RecordingQueue` intercepts background job enqueuing without spawning worker threads or background processes.
4. **Mocked AI & External APIs**:
   - Environment variables `GEMINI_API_KEY=''`, `GROQ_API_KEY=''`, `ANALYSIS_PROVIDER='gemini'`, and `GROQ_FALLBACK_ENABLED='false'` guarantee zero developer quota consumption and no network dependencies.
5. **FastAPI Dependency Overrides**:
   - `app.dependency_overrides[get_db] = test_db`
   - `app.dependency_overrides[get_job_queue] = lambda: job_queue`
   - Standardized test authentication client using mock token `create_access_token({'sub': '123'})`.

---

## 2. Acceptance Fixtures Verification

All acceptance test fixtures are versioned and tracked directly in Git under `backend/test/fixtures/acceptance/`:
- Multi-page contracts (`contract-1.pdf` through `contract-5.pdf`, `contract-24-pages.pdf`)
- Diverse course notes (`course-note-01.pdf` through `course-note-10.pdf`)
- Edge case fixtures: `report-15-pages.pdf`, `insufficient-actions.pdf`, `missing-evidence.pdf`, `textless-page.pdf`
- Structured baseline assertions: `expected.json`

Git tracking was confirmed using `git ls-files backend/test/fixtures/acceptance/`. Deterministic rebuilding and hash-consistency were verified via `backend/tests/test_acceptance_fixtures.py` (all tests passing).

---

## 3. Baseline Failure Resolution

During initial baseline execution, 1 test failure was identified:
- **Test**: `backend/tests/test_upload_validation.py::test_empty_file_rejects_entire_mixed_batch`
- **Symptom**: `assert response.status_code == 422` failed because the API returned `202 Accepted` and initiated a job for a zero-byte file.
- **Root Cause**: `backend/app/core/upload_validation.py` validated file extension and upper size limit (> 5 MB), but lacked an explicit check for empty files (`size_bytes == 0`).
- **Fix Applied**:
  - In `backend/app/core/upload_validation.py`: Added check `if size_bytes == 0: errors.append(error("empty_file", "File must not be empty."))`.
  - In `frontend/lib/upload-validation.js`: Added matching client validation rule `if (file.size === 0) errors.push('Tệp không được rỗng.');`.
  - Synchronized frontend unit and Playwright integration tests in `frontend/tests/upload-validation.spec.js`.
- **Outcome**: The baseline test now passes with HTTP 422 and verifies that zero database records (`Job`, `JobFile`, `Document`) or storage artifacts remain.

---

## 4. Shared Test-Case and Evidence Standard

All Sprint 4 test task handovers (#206, #216, #221) and the consolidated testing report (#209) follow this unified specification format:

### Case Matrix Format

| Case ID | User Story | Case Type | Input / Scenario | Expected Result | Automated Test Location |
|---|---|---|---|---|---|
| `TC-USxx-01` | USxx | Normal | Valid request payload and parameters | 200/202 status, expected structure created | `backend/tests/test_*.py::test_*` |
| `TC-USxx-02` | USxx | Rejection | Invalid format, malformed input, unauthorized user | 400/401/403/422 status, zero residual artifacts | `backend/tests/test_*.py::test_*` |
| `TC-USxx-03` | USxx | Boundary | Boundary values (e.g. 5 MB exact, 5 MB + 1 byte) | Exact boundary handling as specified in BR | `backend/tests/test_*.py::test_*` |

### Required Handover Evidence Checklist
1. **Case Matrix**: At least 3 cases per story covering normal, rejection, and applicable boundary conditions.
2. **Commands**: Exact CLI command lines to run the unit/integration tests.
3. **Execution Output**: Full test execution logs showing test names and pass status.
4. **Deliberate Mutation / Defect Evidence**:
   - Deliberately alter one implementation rule or boundary check.
   - Run the test suite and capture the failing assertion.
   - Revert the code back to correct state and capture the clean passing run.
5. **Pull Request & Commit Links**: Associated commits and PRs.

---

## 5. Clean Baseline Verification Summary

- **Environment**: macOS, Python 3.12.6, pytest 9.1.1
- **Command**:
  ```sh
  cd backend
  .venv/bin/python -m pytest -v
  ```
- **Execution Result**: **612 passed**, 4 skipped, 0 failed.
