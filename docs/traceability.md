# Traceability

Every screen traces back to a feature and forward to the issue that built it.
This table is the single source of truth for Milestone 1 section 6 and for the
Milestone 4 report. Keep it current - a PR that adds a route and does not
update this file should not be approved.

| Route | Purpose | Access | Priority | Feature | Story issue | PR | Status |
|-------|---------|--------|----------|---------|-------------|-----|--------|
| `/` | Next.js product introduction and email sign-in; HttpOnly session and inline errors | G | P0 | F1 / US05 | #62 | Pending | In progress |
| `/workspace` | Protected sign-in destination and logout; document UI follows in #63 | U | P0 | F1 / US05 | #62 / #63 | Pending | In progress |
| `/upload` | File selection, drag/drop and per-file BR01 validation; preserve valid selections | U | P0 | F1 / US06 | #51 / #65 | Pending | In progress |
| `/results/*`, `/documents/*` | Session guard before rendering; feature pages follow in their own tasks | U | P0 | F1 / US05 | Route guard task | Pending | In progress |

**Access codes:** G = guest (not logged in) · U = authenticated user · A = admin

**Status:** Not started / In progress / Done

## Business rules

Numbered, so issues and tests can cite them.

| # | Rule | Enforced where | Tested by |
|---|------|----------------|-----------|
| BR01 | PDF/DOCX/PPTX only; ≤5 files, ≤5 MB per file and ≤50 MB total, checked locally before upload | `frontend/pages/upload.js`, `frontend/lib/upload-validation.js` | `frontend/tests/upload-validation.spec.js` |
| BR07 | Protected routes redirect missing, expired or forged sessions to `/`; backend validates signature and account; document reads return `403` for another owner without exposing data | `frontend/proxy.js`, `pages/workspace.js`, `/auth/me`, `get_current_user_id`, `GET /documents/{document_id}` | `frontend/tests/auth.spec.js`, `frontend/tests/route-guard.spec.js`, `frontend/tests/document-access.spec.js` |

Tasks #62 and #64 run against real FastAPI authentication and document endpoints with an isolated in-memory SQLite database. Task #64 reuses the route-guard tests for guest HTTP 307 and browser redirects, and adds two-account Bearer-token tests for ownership, HTTP 403 with a generic error, unchanged retention on denial, owner HTTP 200, guest HTTP 401, list isolation and missing-document HTTP 404. The `access-control` CI job runs all Playwright tests. MySQL integration and the document workspace remain separate tasks. Review, CI results and merge are still required by the Definition of Done.

Task #65 adds the protected upload selection page and a workspace link. Validation accepts extensions case-insensitively (including empty MIME types), displays per-file rejection badges, preserves valid selections across additions, and revalidates after removal. Limits use 1 MB = 1,048,576 bytes. The 50 MB guard is tested independently because five files of at most 5 MB can only total 25 MB. File transfer, server validation, analysis modes and job creation remain separate work; the existing upload API is a stub.
