# Traceability

Every screen traces back to a feature and forward to the issue that built it.
This table is the single source of truth for Milestone 1 section 6 and for the
Milestone 4 report. Keep it current - a PR that adds a route and does not
update this file should not be approved.

| Route | Purpose | Access | Priority | Feature | Story issue | PR | Status |
|-------|---------|--------|----------|---------|-------------|-----|--------|
| `/` | Next.js product introduction and email sign-in; HttpOnly session and inline errors | G | P0 | F1 / US05 | #62 | Pending | In progress |
| `/workspace` | Protected sign-in destination and logout; document UI follows in #63 | U | P0 | F1 / US05 | #62 / #63 | Pending | In progress |
| `/upload`, `/results/*`, `/documents/*` | Session guard before rendering; feature pages follow in their own tasks | U | P0 | F1 / US05 | Route guard task | Pending | In progress |

**Access codes:** G = guest (not logged in) · U = authenticated user · A = admin

**Status:** Not started / In progress / Done

## Business rules

Numbered, so issues and tests can cite them.

| # | Rule | Enforced where | Tested by |
|---|------|----------------|-----------|
| BR01 | Server independently validates multipart format, count, actual per-file and combined sizes; rejects invalid batches with structured HTTP 422 | `backend/app/api/upload.py`, `backend/app/core/upload_validation.py` | `backend/tests/test_upload_validation.py` (#66) |
| BR07 | Protected routes redirect missing, expired or forged sessions to `/`; backend validates signature and account | `frontend/proxy.js`, `pages/workspace.js`, `/auth/me`, `get_current_user_id` | `frontend/tests/auth.spec.js`, `frontend/tests/route-guard.spec.js` |

Task #62 browser tests run against the real FastAPI authentication endpoints with an isolated in-memory SQLite database. MySQL integration, full document ownership scenarios and the document workspace remain separate tasks. Review, CI results and merge are still required by the Definition of Done.

Task #66 runs backend API tests against the real FastAPI app with a dedicated test signing key, no dependency overrides and no MySQL connection. It covers byte boundaries, format/count/combined-size errors, multiple per-file errors, missing files, Bearer and cookie authentication, and stream rewinding. CI runs `python -m pytest backend/tests -v` in the `Backend upload validation` job. Storage, processing and frontend integration remain separate tasks.
| BR07 | Protected routes redirect missing, expired or forged sessions to `/`; backend validates signature and account; document reads return `403` for another owner without exposing data | `frontend/proxy.js`, `pages/workspace.js`, `/auth/me`, `get_current_user_id`, `GET /documents/{document_id}` | `frontend/tests/auth.spec.js`, `frontend/tests/route-guard.spec.js`, `frontend/tests/document-access.spec.js` |

Tasks #62 and #64 run against real FastAPI authentication and document endpoints with an isolated in-memory SQLite database. Task #64 reuses the route-guard tests for guest HTTP 307 and browser redirects, and adds two-account Bearer-token tests for ownership, HTTP 403 with a generic error, unchanged retention on denial, owner HTTP 200, guest HTTP 401, list isolation and missing-document HTTP 404. The `access-control` CI job runs all Playwright tests. MySQL integration and the document workspace remain separate tasks. Review, CI results and merge are still required by the Definition of Done.
