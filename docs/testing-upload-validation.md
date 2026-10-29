# Issue #204 — US06 upload validation

MB means 1024 × 1024 bytes. Tests reuse the SQLite, temporary storage and
recording queue fixtures in `backend/tests/conftest.py`; no real database,
AI service or credentials are required.

| Case | Automated coverage | Expected result |
|---|---|---|
| TC-US06-01 | `test_valid_extensions_with_generic_mime` | PDF/DOCX/PPTX accepted, case insensitive |
| TC-US06-02 | `test_five_files_at_exact_size_boundary` | Five 5 MB files accepted, total 25 MB |
| TC-US06-03 | `test_disallowed_extensions_even_when_mime_claims_pdf` | Unsupported suffix rejected despite PDF MIME |
| TC-US06-04 | `test_one_byte_above_file_limit` | 5 MB + 1 byte rejected |
| TC-US06-05 | `test_sixth_file_has_its_own_error` | Six files reject the entire batch |
| TC-US06-06 | `test_combined_size_boundary_is_checked_independently` | Isolated defensive guard at 50 MB / 50 MB + 1 byte |
| TC-US06-07 | `test_valid_file_count_boundaries` | Four/five files create one job with corresponding stored files |
| TC-US06-08 | `test_inclusive_file_size_boundary` | 5 MB − 1 byte / exactly 5 MB accepted |
| TC-US06-09 | `test_empty_file_rejects_entire_mixed_batch` | Zero-byte file rejects the whole mixed batch |
| TC-US06-10 | Frontend: `shows per-file size and format errors, keeps valid selections and sends no upload` | Invalid additions preserve valid selections; no POST |

Rejected API cases also verify no Job, JobFile, Document, queued task or stored
file remains through `no_upload_artifacts`, including missing files, invalid
formats, count/size limits, mixed batches and unauthenticated requests.

Five valid files can reach only 5 × 5 MB = 25 MB. They cannot reach the 50 MB
batch limit. TC-US06-06 deliberately uses two oversized files to isolate that
defensive guard: both requests are rejected by the per-file limit, but only
50 MB + 1 byte receives `batch_too_large`. This is not a valid-upload scenario.
The frontend independently tests the same guard and preserves all five accepted
files when a sixth is selected.

Run from the repository root:

```sh
cd backend
.venv/bin/python -m pytest -v tests/test_upload_validation.py tests/test_upload_jobs.py tests/test_auth_authorization.py
cd ../frontend
npm test -- tests/upload-validation.spec.js
```

Use `python` instead of `.venv/bin/python` if the virtual environment is already
activated. Playwright starts its own backend and frontend servers.

Verified locally: **70 backend tests passed; 8 frontend tests passed**.
The new empty-file regression test initially failed: the API returned 202 and
created a job. After adding the empty-file check before persistence, it passes
with 422 and no artifacts. The frontend now reports the same empty-file error.

Credential hygiene: authentication tests generate their test password at runtime;
no fixed password or JWT was added. The tracked working-tree files pass the
credential-pattern and environment/database artifact checks used by CI, and
`git diff --check` passes. This does not constitute a scan of commit history or
GitHub's separate secret-scanning service.

See also [docs/testing-auth-upload.md](testing-auth-upload.md) for the consolidated US05/US06 handover matrix and mutation evidence (#206).
