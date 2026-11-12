# Task #253 — production frontend verification

Date: 2026-11-12. Base checkout: `cb89b4535e37f790d2ae31470632434fca5ec8ec`.
Results below apply to the working-tree changes for #253, not a published release.
Environment: Windows, Node 24.19.0, npm 11.17.0, Next.js 16.4.3, Chromium.

## Implementation

- `render.yaml`: frontend-only Node Web Service, `frontend` root,
  `npm ci && npm run build`, `npm start`, host `0.0.0.0`, platform `PORT`,
  explicit `BACKEND_ORIGIN` at build/runtime, deploy after CI checks pass.
- Production refuses missing/local/malformed backend origins. Startup checks all
  six compiled API rewrites against the runtime origin and requires a rebuild
  when they differ. Development retains the existing loopback fallback.
- SSR and rewrites share origin validation; cookie forwarding and same-origin
  browser requests are preserved. No CORS or browser token-storage changes.
- Proxy body allowance is 30 MiB for five 5 MiB files plus multipart overhead.

## Executed checks

| Check | Result |
|---|---|
| `npm ci` | Passed; 46 packages added, zero reported vulnerabilities |
| `npm run test:config` | 3 passed: invalid production config, development fallback, build/runtime consistency |
| `npm run test:production` | 16 passed; includes `npm run build` and `npm start -- --port 18000` |
| Development Playwright auth/route-guard/proxy suites | 16 passed |
| `npm run build` with `BACKEND_ORIGIN=https://documind-n9ny.onrender.com` | Passed; production pages remain SSR, API rewrites use that HTTPS origin |
| Backend `pytest tests/test_proxy_session.py tests/test_auth_authorization.py -q` | 19 passed |
| Actual `next start` with missing origin, localhost origin, different runtime origin | Each rejected with exit code 1 and a configuration error |
| Start with public backend origin, guest request using forwarded HTTPS/public host | HTTP 307 to relative `/`; no internal host/port leaked into redirect |

Production tests use the real FastAPI routers, JWT/password checks, isolated
SQLite and temporary storage. The backend fixture binds a local non-loopback
IPv4 interface so production rewrite targets do not use localhost. No production
credentials, application database, model calls or deployed user data are used.

Verified browser login errors, login persistence/reload, logout cookie removal,
SSR redirects for missing/forged/expired JWTs and valid-session page access.
API checks cover auth, jobs, upload, search, folders, document list/detail/file.
HTTPS-forwarding simulation verifies a host-only Secure/HttpOnly/SameSite=Lax
cookie travels through Next.js, and SSR forwards the cookie to `/auth/me`.
Backend middleware tests prove an untrusted peer's HTTPS header does not enable
Secure, while a configured trusted peer's header does.

Five files of exactly 5,242,880 bytes each returned HTTP 202 through the upload
rewrite. Job retrieval succeeded. Each downloaded original had the same SHA-256
as its input. `Range: bytes=0-15` returned HTTP 206, the expected Content-Range
and exact bytes. This verifies transport/storage, not AI output quality.

Before the body-size fix, the same upload triggered Next.js's 10 MB truncation
warning and returned HTTP 500 after a proxy socket reset. With 30 MiB, it passed.
The installed Next.js router creates the cloneable body before route matching;
the upload rewrite is affected even though `/api/upload` is outside the page
guard matcher. Therefore a body-size override is necessary for this version.

## Public deployment status / handoff

The supplied backend health URL previously returned HTTP 200 with
`{"status":"ok","database":"ready"}` during this session. This does not prove
which SHA is deployed or validate public session behavior.

No frontend Render service has been created or deployed from this session.
Render access is not connected. Do not mark #253 fully accepted until:

- Render is connected and the reviewed frontend changes are available in the
  deployment repository; record frontend URL, release SHA, successful CI run
  and Render deployment ID/time.
- Backend owner confirms the compatible backend SHA and trusted forwarded-header
  configuration. Verify real HTTPS Secure cookies on the frontend domain,
  login/logout/reload, protected pages and all proxy routes via the public URL.
- Repeat the 25 MiB batch test and document reader/download checks on Render;
  local transport checks do not establish hosting limits or availability.
- Complete teammate review and release checks. Coordinate deployment gating
  and rollback evidence with #252; use the broader acceptance checks in the
  [Render guide](../../deploy-frontend-render.md) for #254/#255.

Logout here means clearing the browser session cookie, matching the existing
stateless JWT flow. These tests do not claim server-side JWT revocation.
