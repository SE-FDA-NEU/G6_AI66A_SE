# Task #257 — live AI and production acceptance follow-up

Verified 13 November 2026, 11:30–11:37 UTC, through https://documind-web-k6i1.onrender.com.
The user supplied the ordinary demo login and a Gemini key. No key, session token
or password is included in these evidence files. The application's normal upload
flow saves the key encrypted to that account; later uploads reused it without
re-entering it. Deployment SHA is still unverified.

| Input / mode | Actual result | Evidence |
|---|---|---|
| Committed report-15-pages.pdf / Bullet | Job 120001 completed 1/1, 11:30:18–11:30:33 UTC (15 s); two source-grounded actions | [Job/HTTP checks](live-ai-verification-257.json) |
| Five committed contract PDFs / Table | Job 120002 completed 5/5, 11:31:31–11:32:13 UTC (42 s); all penalties 0.05% per day, each verified against its own page 3 | Same JSON; original amounts matched 1,200,000,000 VND, 2,500,000,000 VND, 999,999.99 USD, 0.00 VND and 750,000,000 VND |
| Report / Concept with insufficient terminology | Job 120004 completed in 10 s; two supported concepts and explicit limitation instead of invented concepts | Same JSON |
| Synthetic 12-page macroeconomics paper / Concept | Job 120007 completed 11:34:13–11:34:34 UTC (21 s); five concepts, Gemini model gemini-3.5-flash-lite, cache_hit=false | Same JSON |
| Five near-5 MiB synthetic PDFs / Bullet via public proxy | Job 120008 completed 5/5 in 52 s; upload 202 in 6.747 s; 5 × 5,238,784 bytes, 26,193,920 bytes total; all five originals downloaded with matching SHA-256 | [Large batch](large-batch-257.json) |
| Synthetic corpus preparation | 21 documents before large batch, 26 afterward; ten course notes, 24-page contract and source-limitation fixtures added | [Corpus jobs](live-corpus-257.json) |
| Public API checks | 18/18 passed: completed jobs, count, search relevance, source integrity, range, PDF export and two-account denial | [Raw checks](live-ai-verification-257.json) |

The corpus-preparation and supplemental HTTP checks used a Node client through
the frontend domain. They are not evidence that every P0 was completed by browser
clicks. Table/Bullet/Concept entry, upload and result display were exercised in
Orca's browser from the signed-in workspace/upload controls.

Browser citation checks: report citation opened page 6 with source offsets and
returned to the same job 120001. Macro inflation citation opened page 12, selected
page 12 and requested highlighted source bytes in the reader PDF. Searching
“inflation causes” displayed one match and requested the same page with offsets
53–69. The browser showed its direct-highlight notice. This records the reader
state/URL, not a pixel-level claim about every PDF viewer.

Claims containing Vietnamese-formatted numeric values in the Bullet/Concept
outputs were conservatively marked Unverified by the current evidence validator;
the English Table values retained verified source evidence. No override of the
verification state was performed.

## Remaining release blockers

- The deployed WorkspaceHome does not render WorkspaceSearch anywhere. Content
  search works by API but US02 cannot be started by clicking. Restore an explicit
  search entry, review/merge, wait for green main and deploy, then repeat public UI
  acceptance. Existing label-only history search does not satisfy US02.
- Render sign-in succeeds, but the only available workspace has no services.
  Obtain access to the workspace owning both existing DocuMind services to verify
  identical deployed SHAs, CI gates and controlled restart/rollback.
- GitHub credentials lack admin/maintain permissions; required status checks and
  their protection screenshot remain pending administrator configuration.
- Complete private-browser and physical-phone acceptance, exact label-boundary
  fixtures and textless-page fallback. No v1.0 tag or release has been created.

The successful tests apply to the observed deployment, not to an asserted SHA.
No new submission PDF was generated.

## Local regression validation of the US02 entry fix

The new 375 px test failed before the fix because the content-search toggle was
absent. After mounting the existing component behind the toggle, both 1280 px
and 375 px checks passed, including the query, a hit on document 21, page-6
citation URL, no horizontal overflow and return to the upload view. Combined
workspace checks: **7 passed (10.5 s)**. Production build/start with the two new
checks: **2 passed (7.4 s)**. These tests use isolated fixture services and mocked
search responses; the public API relevance results are recorded separately above.

From `frontend`, with the isolated Python environment configured per SETUP:

```bash
npx playwright test tests/workspace-search-entry.spec.js tests/workspace.spec.js --project=chromium
npx playwright test --config playwright.production.config.js tests/workspace-search-entry.spec.js
```

The fix is still awaiting PR review, green main, deployment and public retest.
