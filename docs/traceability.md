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
| BR07 | Protected routes redirect missing, expired or forged sessions to `/`; backend validates signature and account | `frontend/proxy.js`, `pages/workspace.js`, `/auth/me`, `get_current_user_id` | `frontend/tests/auth.spec.js`, `frontend/tests/route-guard.spec.js` |

Task #62 browser tests run against the real FastAPI authentication endpoints with an isolated in-memory SQLite database. MySQL integration, full document ownership scenarios and the document workspace remain separate tasks. Review, CI results and merge are still required by the Definition of Done.
