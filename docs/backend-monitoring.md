# Backend health and monitoring

`GET /health` is public readiness: 200 with `status=ok, database=ready` only after
`SELECT 1` succeeds; 503 otherwise. It returns no credentials or driver errors and
is not cached. The response waits at most two seconds for the probe (excluding
network delivery/event-loop scheduling). The separate one-connection pool uses
one-second pool and two-second connect/read/write limits. An overdue query may
finish after the HTTP deadline; overlapping probes return 503 instead of creating
more waiting threads. This checks API/DB readiness, not provider availability.

## Deployment and log access

Set the platform health path to `/health`. On Render, open the backend service's
Logs tab; filter `app.operations`, `app.services.processing` and
`app.services.job_queue`. Run Uvicorn with `--no-access-log` so raw query strings
(including searches) are not recorded by its access logger. Enable INFO logging
for `app.operations` to collect all request counts with the supplied configuration:
`uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1 --no-access-log --log-config logging.json`.
Request events contain
only method, route template, status and duration, never actual path parameters,
query strings, cookies, headers, bodies, personal details or document contents.
Generic processing/queue failures omit exception text and tracebacks. Do not turn
on SQLAlchemy echo, provider HTTP wire logs, or debug tracebacks in production.

## Detection and response

| Signal | Initial threshold / detection | First response | Owner |
|---|---|---|---|
| Readiness | External check every 60 s; three consecutive failures | Check platform state, DB reachability/TLS and pool capacity | Dang |
| API errors | 5xx >5% over 5 min with at least 20 requests | Inspect sanitized status events; correlate release SHA and rollback if appropriate | Dang |
| API latency | p95 >2 s for 5 min for ordinary JSON routes; track uploads/downloads separately | Check DB latency, pool saturation and host load | Dang |
| Processing | Three failed jobs in 10 min or >10% with at least ten jobs | Review job state and timeout/error codes; keep completed results | Dang |
| AI quota | Any quota/rate-limit code, or repeated provider failures | Check provider dashboard/quota; avoid blind retries; tell PO | Dang, Vu |
| Disk | Usage >80%, write failures or missing source reports | Coordinate storage/backup checks; preserve active files | Duong |

These are proposed initial operational thresholds, not claims that a paid alert
integration or production monitor has already been activated. During the grading
period Dang owns backend triage, Duong owns DB/storage and Tai owns frontend.
Record the actual monitor URL, notification channel and backup responder in the
operations guide before release. Review thresholds after observing real traffic.

Use structured timeout/provider codes already emitted by the processor; do not
copy private exception text, provider keys or source text into incident reports.
Use the provider dashboard for quota usage rather than logging request payloads.

## Verification

From `backend/`: `python -m pytest tests/test_health.py -v`. Tests inject controlled
DB checks, covering healthy/unhealthy/timeout states, overlapping probes, recovery
and sanitized request logs without a real MySQL connection.
