# Authentication (US05) and Upload Validation (US06) Test Evidence Handover

This document delivers the comprehensive test evidence for User Stories **US05** (Sign in and access own documents securely) and **US06** (Validate upload format and size before processing), closing Sprint 4 Task **#206**.

---

## 1. Test Case Matrix

### US05 — Authentication and Cross-Account Authorization

Automated tests are located in `backend/tests/test_auth_authorization.py`. All tests use isolated in-memory SQLite and temporary storage from `conftest.py` without external credentials or services.

| Case ID | Type | Scenario / Input | Expected Result | Automated Test |
|---|---|---|---|---|
| **TC-US05-01** | Normal | Login with valid credentials (`upload@example.com` or `upload_user` + dynamic password) | HTTP 200, returns bearer token, sets HttpOnly cookie `session_token`, sets `Cache-Control: no-store`, `/auth/me` returns user profile without exposing password/hash. | `test_login_accepts_email_and_username` |
| **TC-US05-02** | Rejection | Incorrect password for existing user, or non-existent username (`unknown@example.com`) | HTTP 401 Unauthorized (`Email hoặc mật khẩu không đúng.`), `WWW-Authenticate: Bearer`, zero session cookie set, identical response prevents user enumeration. | `test_bad_credentials_return_same_error_without_session` |
| **TC-US05-03** | Boundary / Rejection | Accessing protected routes (`/auth/me`, `/documents`, `/jobs`, `/search?q=private`) with missing token, forged token, or expired JWT (1 minute in the past) | HTTP 401 Unauthorized (`Token không hợp lệ hoặc đã hết hạn`), `WWW-Authenticate: Bearer`, zero protected data exposed. | `test_protected_routes_reject_invalid_sessions` |
| **TC-US05-04** | Security Boundary | User B (`sub: 124`) attempts to access User A's (`sub: 123`) document metadata, raw file, reader pages, jobs, or PDF export | HTTP 403 on document endpoints (`Access denied`); HTTP 404 on job endpoints (`Job not found`); zero metadata, file content, extracted text or storage paths leaked; list queries return empty arrays; access timestamps and expiration dates remain unchanged. | `test_owner_reads_resources_but_other_account_cannot` |

---

### US06 — Upload Format, File Count, and Size Boundary Validation

Automated backend tests are located in `backend/tests/test_upload_validation.py`; automated frontend Playwright tests are in `frontend/tests/upload-validation.spec.js`. (MB = 1024 × 1024 bytes = 1,048,576 bytes).

| Case ID | Type | Scenario / Input | Expected Result | Automated Test |
|---|---|---|---|---|
| **TC-US06-01** | Normal | Files with allowed extensions in uppercase/mixed case (`report.PDF`, `notes.docx`, `slides.PpTx`) and generic binary MIME | HTTP 202 Accepted, files accepted regardless of case or generic client MIME claims. | `test_valid_extensions_with_generic_mime` |
| **TC-US06-02** | Boundary | Five files at the exact per-file size boundary (5 MB = 5,242,880 bytes each, 25 MB total) | HTTP 202 Accepted, exactly one job created with 5 associated files. | `test_five_files_at_exact_size_boundary` |
| **TC-US06-03** | Rejection | Disallowed extensions (`malware.exe`, `report.pdf.exe`, `README`, `notes.txt`) even when client MIME claims `application/pdf` | HTTP 422 Unprocessable Content (`invalid_format`), rejected before persisting job or files. | `test_disallowed_extensions_even_when_mime_claims_pdf` |
| **TC-US06-04** | Boundary | File sized exactly 1 byte above the limit (5 MB + 1 byte = 5,242,881 bytes) | HTTP 422 Unprocessable Content (`file_too_large`), entire batch rejected. | `test_one_byte_above_file_limit` |
| **TC-US06-05** | Boundary | Batch containing 6 files (exceeding maximum 5 files) | HTTP 422 Unprocessable Content (`too_many_files`), entire batch rejected with zero artifacts. | `test_sixth_file_has_its_own_error` |
| **TC-US06-06** | Boundary | Isolated guard test for 50 MB batch ceiling (50 MB vs 50 MB + 1 byte) | Guard triggers `batch_too_large` error at 52,428,801 bytes. | `test_combined_size_boundary_is_checked_independently` |
| **TC-US06-07** | Boundary | File count boundaries at 4 and 5 valid files | HTTP 202 Accepted, creates exactly one Job with matching stored file count. | `test_valid_file_count_boundaries` |
| **TC-US06-08** | Boundary | File size boundary at 5 MB − 1 byte (5,242,879 B) and exactly 5 MB (5,242,880 B) | HTTP 202 Accepted, inclusive upper boundary accepted. | `test_inclusive_file_size_boundary` |
| **TC-US06-09** | Rejection / Boundary | Zero-byte empty file in a mixed batch (`keep.pdf` + `empty.pdf` of 0 bytes) | HTTP 422 Unprocessable Content (`empty_file`), entire batch rejected, `no_upload_artifacts` verifies zero database rows (`Job`, `JobFile`, `Document`) and zero disk artifacts remain. | `test_empty_file_rejects_entire_mixed_batch` |
| **TC-US06-10** | UI Integration | Selecting invalid format, empty file, and oversize file alongside valid files in the browser | Preserves valid selections, displays per-file error badges ("Chỉ chấp nhận PDF, DOCX hoặc PPTX.", "Tệp không được rỗng.", "Tệp vượt quá 5 MB."), and blocks upload POST request. | Playwright: `shows per-file size and format errors, keeps valid selections and sends no upload` |

---

## 2. Deliberate Mutation and Defect Detection Evidence

To prove that the automated test suite effectively detects defects and enforces system rules, two deliberate mutations were applied to the application code.

### Defect Mutation 1 (US06): Bypassing Empty File Validation

- **Deliberate Mutation**: In `backend/app/core/upload_validation.py`, disabled the zero-byte check:
  ```python
  # Deliberate mutation:
  if False and size_bytes == 0:
      errors.append(error("empty_file", "File must not be empty."))
  ```
- **Failing Test Output**:
  ```text
  FAILED backend/tests/test_upload_validation.py::test_empty_file_rejects_entire_mixed_batch
  ERROR backend/tests/test_upload_validation.py::test_empty_file_rejects_entire_mixed_batch
  
  AssertionError: assert 202 == 422
  + where 202 = <Response [202 Accepted]>.status_code
  
  ERROR at teardown of test_empty_file_rejects_entire_mixed_batch:
  AssertionError: assert 1 == 0
  + where 1 = db.query(Job).count()
  ```
- **Restored Code & Passing Output**:
  Restored `if size_bytes == 0: errors.append(error("empty_file", "File must not be empty."))`:
  ```text
  backend/tests/test_upload_validation.py::test_empty_file_rejects_entire_mixed_batch PASSED [100%]
  1 passed, 25 deselected in 0.07s
  ```

### Defect Mutation 2 (US05): Invalid Credential Status Code Mutation

- **Deliberate Mutation**: In `backend/app/api/auth.py`, mutated HTTP 401 Unauthorized to HTTP 400 Bad Request on invalid login attempts:
  ```python
  # Deliberate mutation:
  raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,  # mutated from 401
      detail="Email hoặc mật khẩu không đúng.",
  )
  ```
- **Failing Test Output**:
  ```text
  FAILED backend/tests/test_auth_authorization.py::test_bad_credentials_return_same_error_without_session[upload@example.com-incorrect-password]
  FAILED backend/tests/test_auth_authorization.py::test_bad_credentials_return_same_error_without_session[unknown@example.com-US05-test-password]
  
  AssertionError: assert 400 == 401
  + where 400 = <Response [400 Bad Request]>.status_code
  ```
- **Restored Code & Passing Output**:
  Restored `status_code=status.HTTP_401_UNAUTHORIZED`:
  ```text
  backend/tests/test_auth_authorization.py::test_bad_credentials_return_same_error_without_session[upload@example.com-incorrect-password] PASSED [ 50%]
  backend/tests/test_auth_authorization.py::test_bad_credentials_return_same_error_without_session[unknown@example.com-US05-test-password] PASSED [100%]
  2 passed, 15 deselected in 0.75s
  ```

---

## 3. Test Execution Commands and Full Output

### Backend Test Execution
Run from repository root:
```sh
cd backend
.venv/bin/python -m pytest -v tests/test_auth_authorization.py tests/test_upload_validation.py
```

**Output**:
```text
============================= test session starts ==============================
platform darwin -- Python 3.12.6, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/phandangvu/Desktop/SE
collected 43 items

backend/tests/test_auth_authorization.py::test_login_accepts_email_and_username[upload@example.com] PASSED [  2%]
backend/tests/test_auth_authorization.py::test_login_accepts_email_and_username[upload_user] PASSED [  4%]
backend/tests/test_auth_authorization.py::test_bad_credentials_return_same_error_without_session[upload@example.com-incorrect-password] PASSED [  6%]
backend/tests/test_auth_authorization.py::test_bad_credentials_return_same_error_without_session[unknown@example.com-US05-test-password] PASSED [  9%]
backend/tests/test_auth_authorization.py::test_protected_routes_reject_invalid_sessions[missing-/auth/me] PASSED [ 11%]
backend/tests/test_auth_authorization.py::test_protected_routes_reject_invalid_sessions[missing-/documents] PASSED [ 13%]
backend/tests/test_auth_authorization.py::test_protected_routes_reject_invalid_sessions[missing-/jobs] PASSED [ 16%]
backend/tests/test_auth_authorization.py::test_protected_routes_reject_invalid_sessions[missing-/search?q=private] PASSED [ 18%]
backend/tests/test_auth_authorization.py::test_protected_routes_reject_invalid_sessions[forged-/auth/me] PASSED [ 20%]
backend/tests/test_auth_authorization.py::test_protected_routes_reject_invalid_sessions[forged-/documents] PASSED [ 23%]
backend/tests/test_auth_authorization.py::test_protected_routes_reject_invalid_sessions[forged-/jobs] PASSED [ 25%]
backend/tests/test_auth_authorization.py::test_protected_routes_reject_invalid_sessions[forged-/search?q=private] PASSED [ 27%]
backend/tests/test_auth_authorization.py::test_protected_routes_reject_invalid_sessions[expired-/auth/me] PASSED [ 30%]
backend/tests/test_auth_authorization.py::test_protected_routes_reject_invalid_sessions[expired-/documents] PASSED [ 32%]
backend/tests/test_auth_authorization.py::test_protected_routes_reject_invalid_sessions[expired-/jobs] PASSED [ 34%]
backend/tests/test_auth_authorization.py::test_protected_routes_reject_invalid_sessions[expired-/search?q=private] PASSED [ 37%]
backend/tests/test_auth_authorization.py::test_owner_reads_resources_but_other_account_cannot PASSED [ 39%]
backend/tests/test_upload_validation.py::test_valid_extensions_with_generic_mime[report.PDF] PASSED [ 41%]
backend/tests/test_upload_validation.py::test_valid_extensions_with_generic_mime[notes.docx] PASSED [ 44%]
backend/tests/test_upload_validation.py::test_valid_extensions_with_generic_mime[slides.PpTx] PASSED [ 46%]
backend/tests/test_upload_validation.py::test_five_files_at_exact_size_boundary PASSED [ 48%]
backend/tests/test_upload_validation.py::test_disallowed_extensions_even_when_mime_claims_pdf[malware.exe] PASSED [ 51%]
backend/tests/test_upload_validation.py::test_disallowed_extensions_even_when_mime_claims_pdf[report.pdf.exe] PASSED [ 53%]
backend/tests/test_upload_validation.py::test_disallowed_extensions_even_when_mime_claims_pdf[README] PASSED [ 55%]
backend/tests/test_upload_validation.py::test_disallowed_extensions_even_when_mime_claims_pdf[notes.txt] PASSED [ 58%]
backend/tests/test_upload_validation.py::test_one_byte_above_file_limit PASSED [ 60%]
backend/tests/test_upload_validation.py::test_sixth_file_has_its_own_error PASSED [ 62%]
backend/tests/test_upload_validation.py::test_combined_size_boundary_is_checked_independently[52428800-False] PASSED [ 65%]
backend/tests/test_upload_validation.py::test_combined_size_boundary_is_checked_independently[52428801-True] PASSED [ 67%]
backend/tests/test_upload_validation.py::test_reports_all_failures_and_identifies_duplicate_filenames_by_index PASSED [ 69%]
backend/tests/test_upload_validation.py::test_single_file_can_report_multiple_reasons PASSED [ 72%]
backend/tests/test_upload_validation.py::test_missing_files_has_structured_error PASSED [ 74%]
backend/tests/test_upload_validation.py::test_swagger_files_schema_is_binary_array PASSED [ 76%]
backend/tests/test_upload_validation.py::test_unauthenticated_upload_rejected[None] PASSED [ 79%]
backend/tests/test_upload_validation.py::test_unauthenticated_upload_rejected[Bearer forged-token] PASSED [ 81%]
backend/tests/test_upload_validation.py::test_cookie_session_is_supported PASSED [ 83%]
backend/tests/test_upload_validation.py::test_reads_actual_bytes_and_rewinds_even_after_rejection[16] PASSED [ 86%]
backend/tests/test_upload_validation.py::test_reads_actual_bytes_and_rewinds_even_after_rejection[5242881] PASSED [ 88%]
backend/tests/test_upload_validation.py::test_valid_file_count_boundaries[4] PASSED [ 90%]
backend/tests/test_upload_validation.py::test_valid_file_count_boundaries[5] PASSED [ 93%]
backend/tests/test_upload_validation.py::test_inclusive_file_size_boundary[5242879] PASSED [ 95%]
backend/tests/test_upload_validation.py::test_inclusive_file_size_boundary[5242880] PASSED [ 97%]
backend/tests/test_upload_validation.py::test_empty_file_rejects_entire_mixed_batch PASSED [100%]

======================= 43 passed, 194 warnings in 4.05s =======================
```

### Frontend Test Execution
Run from repository root:
```sh
cd frontend
npm test -- tests/upload-validation.spec.js
```

**Output**:
```text
Running 8 tests using 1 worker

  ✓ BR01 checks file size in bytes and permits case-insensitive allowed extensions (5ms)
  ✓ BR01 independently checks the inclusive 50 MB batch boundary (3ms)
  ✓ upload page › accepts PDF, DOCX and PPTX even with missing MIME types (1.6s)
  ✓ upload page › accepts five files at exactly 5 MB and rejects a sixth without clearing them (3.2s)
  ✓ upload page › shows per-file size and format errors, keeps valid selections and sends no upload (1.3s)
  ✓ upload page › revalidates rejected files when a slot is freed without displacing accepted files (927ms)
  ✓ upload page › drag and drop validates files and supports selecting the same file after removal (960ms)
  ✓ upload page › mobile layout accommodates long filenames and keeps removal accessible (913ms)

  8 passed (16.4s)
```

---

## 4. Credential Hygiene and Secret Protection

- **No Stored Credentials**: Authentication tests use ephemeral credentials generated at test runtime with `secrets.token_urlsafe(24)` in `backend/tests/test_auth_authorization.py`.
- **Zero Real Secrets**: Test environment config in `backend/tests/conftest.py` uses mock static keys (`unused-test-value`, `isolated-upload-validation-test-key`) and zeroed AI API keys (`GEMINI_API_KEY=''`, `GROQ_API_KEY=''`).
- **Secret Leaks Prevention**: Tests explicitly assert that sensitive data (`password`, `password_hash`, internal absolute storage paths) are never present in response bodies or HTTP headers.
- **Git Hygiene**: Verified with `git diff --check`, ensuring zero trailing whitespace or credential leaks.

---

## 5. Linked Pull Requests and Commits

- **PR #222**: `203 add authentication and authorization tests` (Closes #203) — Commits `44b082a`, `56c56b2`
- **PR #223**: `204 upload validation` (Closes #204) — Commit `1164776`
- **PR #233**: `#205 Verify isolated pytest environment and fix baseline failure` (Closes #205) — Commit `a1a1a25`
- **PR for #206**: Hand over authentication and upload test evidence
