# CI and main protection

CI runs on pushes to main and pull requests into main. Both Python environments
use 3.12; Node uses 24 with the committed npm lockfile. Required checks to select
in the main ruleset are `Python tests`, `Node build and tests`, and
`No secrets committed`. They run full pytest, Playwright Chromium/Android/WebKit
iOS, the production Next build, and credential/file checks. Native Python
readers and bundled Noto fonts replace LibreOffice; no current test invokes it.

## Protection audit (12 November 2026)

The active organization ruleset [main-protection](https://github.com/SE-FDA-NEU/G6_AI66A_SE/rules/21296815)
targets the default branch, blocks deletion/force pushes and requires a PR with
one approving review. It currently has **no required status checks**. The
Dangtooo account has push/triage access but no admin/maintain permission, so it
cannot configure that organization ruleset. An organization administrator must
add the three checks above and capture the final settings screenshot. A PR
approval alone does not enforce a successful CI run.

After this PR is approved and merged, record the green **main** run URL, SHA and
elapsed duration from Actions (start to completion), together with that screenshot.
A green PR run is validation of the candidate, not evidence of a merged main run.
Do not bypass failed checks to obtain this evidence.

## Existing main failure

[Run 43217738816](https://github.com/SE-FDA-NEU/G6_AI66A_SE/actions/runs/43217738816)
failed 12 upload assertions because Linux `rglob('*.*')` included the empty
`.analysis-cache` directory created by storage initialization. The assertion now
rejects every remaining file recursively, including hidden cache/partial files,
while permitting empty infrastructure directories. Production validation is not
relaxed. The run had 707 passes and five skips before the assertion fix.

## Review and release verification

1. Open the PR's Checks tab: all three jobs must succeed without deselection.
2. Review the full named pytest/JUnit and Playwright/build artifacts.
3. Obtain at least one teammate approval and merge through the protected PR flow.
4. Verify the new main run, then bind deployment to that exact successful SHA.
5. Record duration and required-check settings for the operations guide owner.

The main-green link and final protection screenshot remain pending the merge and
administrator change; no deployment or production protection change is claimed.

## Updated main evidence (13 November 2026)

[Run 43387604003](https://github.com/SE-FDA-NEU/G6_AI66A_SE/actions/runs/43387604003)
succeeded on main SHA `ee290ee5206db80f7e0d4e6116689f18404ec577`.
Elapsed time was 6 min 6 s (07:41:58–07:48:04 UTC). All three jobs succeeded.
The Node job now includes production configuration/build/session smoke tests.
The effective-rules API still reports PR approval, deletion and force-push
protection, with no required status checks. Final administrator configuration
and screenshot are still pending; no production deploy SHA is inferred from CI.
See [operations](operations.md) and [release acceptance](release-acceptance.md).
