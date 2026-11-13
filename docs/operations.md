# Production operations

## 1. How to run and release

Published release: [v1.0](https://github.com/SE-FDA-NEU/G6_AI66A_SE/releases/tag/v1.0), main SHA `0431a5d463295f6acd38b87c367e79c47a7037cc`.

Public app: https://documind-web-k6i1.onrender.com. Frontend and FastAPI backend run on Render; backend: https://documind-n9ny.onrender.com. MySQL-compatible TiDB and persistent backend files are owned by Duong. Platform configuration still requires owner verification.

Run locally using [SETUP](SETUP.md). Release: reviewed PR → merge → successful main CI → deploy the same SHA to both services. The frontend blueprint specifies `checksPass`; Dang must verify the backend gate and Tai the live frontend setting. Keep one backend instance/worker; stop the old process tree before replacement.

Rollback: stop traffic, select the last verified compatible SHA in both Render services, redeploy, then check login, DB, files and citations. Keep the same DB/storage. If schema changes are incompatible, stop and restore into a separate environment before switching; code rollback does not restore data. Record both deploy IDs and smoke results in [release acceptance](release-acceptance.md).

## 2. The CI pipeline

| Step | Checks |
|---|---|
| Setup/install | Python 3.12; Node 24; pip development requirements; npm lockfile; Chromium/WebKit |
| Python tests | Full pytest; JUnit artifact |
| Node build and tests | Desktop/Android/iOS Playwright; production configuration, build and session tests; reports |
| No secrets committed | Credential patterns; no tracked environment files or database dumps |
| Artifacts | Test/build reports retained 14 days |

Latest verified green main: [43412489569](https://github.com/SE-FDA-NEU/G6_AI66A_SE/actions/runs/43412489569), SHA `0431a5d463295f6acd38b87c367e79c47a7037cc`. Measured start-to-completion: **6 min 20 s**, 2026-11-13 10:52:34–10:58:54 UTC. Refresh this evidence for the release SHA.

[Main protection](https://github.com/SE-FDA-NEU/G6_AI66A_SE/rules/21296815) requires one PR approval and blocks force pushes/deletion. API inspection found no required status checks. An organization administrator must require all three checks and supply a settings screenshot; screenshot and enforcement remain release blockers (#251).

## 3. Monitoring

Backend `/health` runs bounded `SELECT 1`: 200 ready, 503 unavailable; it does not check AI. Verify `/health` on the public frontend too. Render service Logs contain sanitized request route/status/duration and processing state/error codes. Never log passwords, tokens, keys, personal data, document contents or search text. Use the [logging configuration](backend-monitoring.md).

| Signal | Detection and response | Owner |
|---|---|---|
| Health | Check every 60 s; alert after three failures; inspect service/DB | Dang |
| Error rate | 5xx >5% over 5 min, ≥20 requests; inspect logs/release | Dang |
| Response time | Ordinary JSON p95 >2 s over 5 min; inspect DB/load | Dang |
| Jobs/quota/disk | Three job failures/10 min, any quota error, disk >80%; inspect provider/storage | Dang / Duong |

Thresholds are proposed. Monitor URL, notification channel and backup responder must be verified before acceptance; no active alert integration is claimed.

## 4. Known risks and technical debt

| Item | Layer | What could happen | Plan |
|---|---|---|---|
| In-memory queue | code | Restart interrupts work; concurrency has no explicit admission cap | #249; single process, failed-job resubmission; capacity verification #248 |
| Persistent files | data | DB survives while originals disappear | #246; mounted storage and coordinated restore rehearsal |
| AI availability | infrastructure | Quota errors or partial batch failures | #254; retest five-file batch after #269 |
| Required CI checks absent | infrastructure | Broken merge can bypass checks | #251; administrator adds three required checks |
| Public acceptance incomplete | tests | Local passes hide hosting/browser failures | #257; live AI/API passes recorded, full click-only P0 acceptance pending |
| Missing content-search entry | code | US02 cannot start from workspace despite a working API | #257; restore the existing search component behind an explicit button; deploy and retest |
| Missing deployment/alert evidence | docs | Operator cannot identify release or detect outage | #256; owners verify service settings and evidence |
| Cold start | infrastructure | First request is slow | Accepted: grading brief permits slow initial visits; check before demo |

## 5. Maintenance plan

| Area | What to do | Owner | How often |
|---|---|---|---|
| Bugs | Triage, reproduce, fix through reviewed green PR | Vu coordinates; component owner fixes | Daily and each report |
| Dependencies | Review advisories/lockfiles; test before update | Dang backend; Tai frontend | Weekly and urgent advisories |
| Backups | Quiesce writes/workers/retention; coordinated MySQL + files backup; encrypt off-host copy | Duong | Daily and before release/schema changes |
| Monitoring | Review health, errors, latency, quotas, disk; respond | Dang; Duong storage | Daily; alerts continuously once configured |
| Documentation | Recheck URLs, SHAs, commands, accounts, ownership | Vu with Dang/Duong/Tai | Each release and weekly |

From `backend`, use `python -m app.services.storage_ops --backup`, then `--restore-test /secure/bundle`. The latter verifies a separate temporary SQLite restore, not MySQL recovery. Rehearse the SQL dump in an empty isolated MySQL database with matching files, then `--verify` and citation checks before cutover. Never restore over live data blindly. Proposed retention: seven daily encrypted backups; Duong must approve and enforce deletion/access controls.

Documents expire 30 days after successful open/download/update; warn seven days beforehand. Listing/polling does not renew expiry. Cleanup defaults to hourly batches of 100. Backups must follow deletion policy. Queue shutdown defaults to 10 s grace plus 8 s cleanup; host shutdown must allow longer. See [restart limits](processing-restart.md).

## 6. Lessons learned

| Incident | Fix | Future change |
|---|---|---|
| Linux CI counted empty `.analysis-cache` as leftover upload | Assert remaining files recursively, allow empty infrastructure directories (#263) | Include hidden paths in cleanup checks |
| Mobile CI waited for hidden folder controls | Wait for mobile toggle/sidebar visibility ([M4 report](testing.md)) | Test responsive state transitions in CI |
| Five-file proxy upload exceeded Next's 10 MB default | Set 30 MiB proxy allowance and add 25 MiB production test (#267) | Verify platform limits before deployment |
| Public batch completed only 3/5 files | #269 changes analysis/key handling; live follow-up completed five near-5 MiB files 5/5 ([evidence](evidence/m5/live-acceptance-257.md)) | Preserve failed-job evidence and require live AI acceptance (#254) |

## 7. Availability commitment and verification

Proposed accountable coordinator: Vu (@PhanDangVu), until grades are published. The publication date is unspecified; this is an event-based end date. Vu must confirm the commitment, keep hosting/billing active and arrange backup cover. Dang verifies backend/gates/alerts; Duong verifies MySQL/storage/backups; Tai verifies frontend/proxy; Vu signs release acceptance. Owner confirmations and the final protection screenshot remain pending. Release [v1.0](https://github.com/SE-FDA-NEU/G6_AI66A_SE/releases/tag/v1.0) was published on 13 November 2026 from green main `0431a5d463295f6acd38b87c367e79c47a7037cc`.
