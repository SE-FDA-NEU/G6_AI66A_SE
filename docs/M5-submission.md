Running app: https://documind-web-k6i1.onrender.com

# Milestone 5 — Team 06 submission

**Draft — do not upload to LMS yet.** Public smoke checks passed, but full P0 acceptance, deployed SHAs and `v1.0` publication are pending. The PDF explicitly preserves this status.

## 7. What to submit here

Submit one file named **`Team06_M5.pdf`**. The first line identifies the running app. The table below contains every field required by section 7; no private credentials belong in the PDF.

| Field | Value |
|---|---|
| Running app | https://documind-web-k6i1.onrender.com |
| Team | Team 06 — DocuMind |
| Members | To Hien Hai Dang (11247271); Phan Dang Vu (11247373); Bui Dang Duong (11247274); Nguyen Bao Tai (11247348) |
| Scrum Master | @taibaonguyen (Sprint 5) |
| Repository | https://github.com/SE-FDA-NEU/G6_AI66A_SE |
| Release v1.0 | PENDING — not published. Expected URL after verified release: https://github.com/SE-FDA-NEU/G6_AI66A_SE/releases/tag/v1.0 |
| Latest green CI run on main | https://github.com/SE-FDA-NEU/G6_AI66A_SE/actions/runs/43412489569 |
| Test accounts | See the first screen of README.md. PENDING: README currently has no verified production demo accounts; task #255 must supply them. Local seed credentials failed production login. |

The verified main SHA is `0431a5d463295f6acd38b87c367e79c47a7037cc`; all three CI jobs passed. This does not establish which SHA Render is running. Refresh the CI URL after the final merge and deployment.

## 6. Submission workflow

| Step | Required action | Actual state / evidence |
|---|---|---|
| 1. Deploy early | Connect both production services to main and deploy only after CI passes. Keep the public HTTPS URL online until grades are published. | App is reachable. Render blueprint specifies checksPass for frontend. Live service settings, both deployed SHAs and backend CI gate remain unverified. The authenticated Render account currently has an empty workspace and no services. |
| 2. Branch and commit | Commit docs/operations.md and production README changes on a branch. | Operations committed in PR #270. Follow-up checks/docs in PR #271. Production README changes and verified demo accounts remain task #255. |
| 3. Review and merge | Another member uses Review changes to leave a substantive comment, approve, then merge into main. A plain issue/PR comment is not a formal review. | PR #270 approved by Dangtooo and merged; the approval body was empty, so a substantive review comment is not evidenced. PR #271 has green CI but is still open at this audit. |
| 4. Wait and accept | Wait for green main CI and deployment. In private laptop/phone browsers, complete all nine P0 stories by clicking from the landing page; verify reload and restart persistence. | Read-only public checks 11/11; registration, session reload and 375 px six-file validation checked. Full P0, live AI, physical phone/private window and controlled restart remain pending. See docs/release-acceptance.md. |
| 5. Publish release | After acceptance, create v1.0 on the exact green-main SHA running on both services and publish three release-note lines. Never move an existing published tag silently. | PENDING. No tag/release created. Record accepted SHA, frontend/backend deploy IDs, UTC acceptance time and CI URL first. |
| 6. Export and submit | Export the section 7 block as Team06_M5.pdf; check all fields and links, then upload that single PDF to LMS. | Draft PDF generated in docs/Team06_M5.pdf, with this workflow as page 2. Do not upload until all pending fields are resolved. No LMS submission performed. |

## Rebuild the PDF

From the repository root, using the backend development environment:

```bash
python scripts/export_m5_submission.py
```

The exporter reads these tables and writes `docs/Team06_M5.pdf`. It uses the bundled Noto Sans fonts and ReportLab already listed in backend requirements. Every table has an outer box and internal grid lines; no table is open at its sides. Page 1 starts with the app URL and contains the required submission block; page 2 contains the six-step workflow.

Before final export, replace pending values only with verified facts, update the latest green main CI link and deployed/tagged SHA, confirm README demo accounts, complete the formal review and full public acceptance, and remove the draft notice only when accurate. The exporter marks the PDF draft while this document contains PENDING or the draft notice.
