# US04 / US08 / US09 test handover

Evidence captured on 29 October 2026 (Asia/Bangkok), on Windows with Python 3.12.6 and pytest 9.1.1. Story scope comes from [requirements.md](requirements.md). Tests use isolated SQLite, generated PDFs and injected analyzers; no real AI-provider quota or production database is used.

## Case matrix

The [complete case matrix](testing-evidence/case-matrix.md) maps **80 unique case IDs to 102 actual pytest invocations**, including normal, rejection and applicable boundary scenarios. [cases.json](testing-evidence/cases.json) records the exact node ID and parameter values for every invocation; [collection.txt](testing-evidence/collection.txt) is the actual collection output. Each case ID can be selected with `pytest -k TC-US04-02`, for example.

| Story | IDs | Unique IDs / invocations | Coverage |
|---|---|---|---|
| US04 | TC-US04-01 through TC-US04-56 | 56 / 65 | Label confidence and unchanged human metadata/folder; concept validation; search, physical page navigation and PDF highlighting. |
| US08 | TC-US08-01 through TC-US08-11 | 11 / 17 | Valid/missing/invalid evidence across bullet, table and concept modes; persisted independent document citations; stale/wrong/mixed sources. |
| US09 | TC-US09-01 through TC-US09-13 | 13 / 20 | Saved citation opens exact source and visible highlight; invalid citation rejection; first/last page, invalid page inputs and textless-page fallback. |

Representative normal, rejection and boundary cases (all are in the complete matrix):

| Story / case | Kind | Test and parameter | Expected result |
|---|---|---|---|
| TC-US04-03 | Normal | `test_confidence_threshold_values_persisted(confidence=0.81, confidence_level='high')` | Persist high confidence without moving folder or overriding human decisions. |
| TC-US04-04 | Rejection | `test_invalid_mocked_label_is_not_published(label={'ai_label': '', 'ai_confidence': 0.8})` | `invalid_result`; previous metadata preserved. |
| TC-US04-02 | Boundary | `test_confidence_threshold_values_persisted(confidence=0.80, confidence_level='high')` | Exactly 80% is high, across both folder states and both review states. |
| TC-US08-01 | Normal | `test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode(state='valid')`, mode=`bullet/table/concept` | Correct source document/page retained and claim verified. |
| TC-US08-03 | Rejection / boundary | Same test, `state='invalid'`, evidence points to textless page 5 | Invalid evidence rejected; claim remains Unverified with no trusted page link. |
| TC-US08-05 | Boundary | `test_two_documents_supporting_one_bullet_claim_persist_distinct_citations(second_page=3)` | Same fact retains doc1/page1 and doc2/page3 independently through DB persistence and reload. |
| TC-US09-01 | Normal | `test_saved_citation_opens_matching_document_page_and_visible_highlight(source_page=2)` | Same saved job/document; visible highlight only on the cited page. |
| TC-US09-02 | Rejection | `test_invalid_citation_is_removed_from_saved_reader_summary(invalid_source='page')` | Nonexistent page cannot become a trusted saved citation. |
| TC-US09-05 / 06 | Boundary | `test_citation_page_selects_readable_original_without_changing_source(page=1/3)`, endpoint=`file/rendered-file` | First/last page accepted with correct headers and unchanged source PDF. |

US04-01/02/03 each expand into four combinations: assigned/unassigned folder x confirmed/needs_review. US08-01/02/03 each run in three analysis modes. US09-05 through US09-11 each run on both readable-file endpoints. "Rejection" for evidence means rejecting the untrusted reference and persisting Unverified, rather than necessarily returning an HTTP error or failing the job.

## Commands and actual results

Run from the repository root after installing `backend/requirements-dev.txt`. On Windows use `backend/.venv/Scripts/python.exe`; on Linux use the activated environment's `python`.

```powershell
$py = 'backend/.venv/Scripts/python.exe'
$storyTests = @(
  'backend/tests/test_document_metadata_api.py',
  'backend/tests/test_concept_processing.py',
  'backend/tests/test_reader_extraction.py',
  'backend/tests/test_reader_presentation.py',
  'backend/tests/test_evidence.py',
  'backend/tests/test_evidence_persistence.py',
  'backend/tests/test_document_file.py'
)

# Generate exact ID/input mapping and inspect collection.
& $py -m pytest @storyTests -k 'TC-US04 or TC-US08 or TC-US09' --collect-only -q -p no:cacheprovider -p scripts.story_matrix_plugin

# Use a fresh system-temp directory: pytest may delete its --basetemp contents.
$runTemp = Join-Path ([IO.Path]::GetTempPath()) ('documind-' + [guid]::NewGuid())
& $py -m pytest @storyTests -k 'TC-US04 or TC-US08 or TC-US09' -vv --tb=short -p no:cacheprovider --basetemp $runTemp

$hygieneTemp = Join-Path ([IO.Path]::GetTempPath()) ('documind-hygiene-' + [guid]::NewGuid())
& $py -m pytest backend/tests/test_repository_hygiene.py -vv --tb=short -p no:cacheprovider --basetemp $hygieneTemp
& $py scripts/check_repository_hygiene.py
& $py scripts/check_repository_hygiene.py --revision HEAD
git diff --check
```

Actual captured results, not illustrative output. Log line endings and trailing whitespace are normalized for Git; assertion text, results and exit codes are preserved:

| Run | Actual output | Exit | Full output |
|---|---|---|---|
| Collection | `102/172 tests collected (70 deselected) in 0.67s` | 0 | [collection.txt](testing-evidence/collection.txt) |
| Deliberately broken 80% threshold | `4 failed, 17 deselected, 27 warnings in 8.45s` | 1 | [mutation-fail.txt](testing-evidence/mutation-fail.txt) |
| Restored code, all selected story cases | `102 passed, 70 deselected, 714 warnings in 43.83s` | 0 | [restored-pass.txt](testing-evidence/restored-pass.txt) |
| Hygiene guard, isolated Git index | `5 passed, 1 warning in 3.55s` | 0 | [hygiene.txt](testing-evidence/hygiene.txt) |
| Actual pre-push hook, historical artifact commit / clean HEAD | Rejected `bf111d8` (20 generated PDFs); accepted clean HEAD | 1 / 0 | [hook-check.txt](testing-evidence/hook-check.txt) |

The 70 deselected tests are outside this selected case matrix. This is backend/API/PDF evidence; it does not claim a browser click test of Back to Results or its textless-page explanation. US09-01 checks the saved job association and rendered highlight; US09-12/13 check readable textless pages and rejection of fabricated spans. Existing warnings are retained in the raw output; warning-free execution and the full repository/browser suite were not acceptance claims for this handover.

## Deliberate break, failure and restoration

The tested rule is that a confidence of **0.80 is high**. In [result_persistence.py](../backend/app/services/result_persistence.py), change only this comparison:

```diff
- 'high' if document.ai_confidence >= .8 else 'low'
+ 'high' if document.ai_confidence > .8 else 'low'
```

Run the boundary subset with the mutation applied:

```powershell
$mutationTemp = Join-Path ([IO.Path]::GetTempPath()) ('documind-mutation-' + [guid]::NewGuid())
& $py -m pytest backend/tests/test_document_metadata_api.py -k TC-US04-02 -vv --tb=short -p no:cacheprovider --basetemp $mutationTemp
```

All four folder/review combinations failed with `{'confidence_level': 'low'} != {'confidence_level': 'high'}`. The capture used a `try/finally` block to restore the original file bytes before running the complete passing selection. [mutation.json](testing-evidence/mutation.json) records the identical SHA-256 before and after restoration, `ee6f5aa1e6bc11bc6f09b03be8de9e9b5d0996a820de2ea854cf0459b316af31`. The deliberate defect was never committed. Full commands, node IDs, assertions and exit codes are in the linked raw output.

## Repository hygiene

- Test source belongs in `backend/tests/`. Existing intentional acceptance PDFs live in `backend/test/fixtures/acceptance/` and remain tracked.
- Generated PDFs/uploads belong in pytest `tmp_path`, normally outside the checkout. Reports belong in ignored `test-results/`; temporary local directories matching `.tmp*/`, pytest/Python caches and coverage output are ignored.
- `.gitignore` alone cannot block a force-add or an already tracked artifact. [check_repository_hygiene.py](../scripts/check_repository_hygiene.py) checks the index before commits, committed trees before pushes, and CI. The tests use an isolated Git index to prove that force-added generated paths are rejected while intentional PDFs are allowed.
- Versioned [pre-commit](../.githooks/pre-commit) and [pre-push](../.githooks/pre-push) hooks are enabled in this checkout. After a fresh clone, run `git config core.hooksPath .githooks`. Hooks require Python on PATH. They check the version being committed/pushed; historical artifacts in ancestor commits do not block a clean current tree. Local hooks can be bypassed; CI supplies a second check. Merge blocking still depends on the repository's required-check settings.
- Raw text evidence under `docs/testing-evidence/` is intentional handover documentation. Runtime PDFs and uploads are excluded. Removing tracked files in the cleanup commit does not rewrite Git history.

## Commits and PRs

PR-to-commit mapping was verified against GitHub `refs/pull/*/head` using `git ls-remote origin 'refs/pull/*/head'`.

| Scope | Commit | PR |
|---|---|---|
| US04 label/concept validation | [c3ad0b7](https://github.com/SE-FDA-NEU/G6_AI66A_SE/commit/c3ad0b71504781e3683d43a48529324a8be20258) | [#224](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/224) |
| US04 search/navigation/highlights | [bf111d8](https://github.com/SE-FDA-NEU/G6_AI66A_SE/commit/bf111d89d114d830e4f87b5415550fb0246fdbe1) | [#225](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/225) |
| US08 evidence integrity | [53e992a](https://github.com/SE-FDA-NEU/G6_AI66A_SE/commit/53e992a1c2ff262a9476c5ead51c4c9599e4eff0) | [#226](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/226) |
| US09 citation reader navigation | [d340083](https://github.com/SE-FDA-NEU/G6_AI66A_SE/commit/d340083c99f22e045d18f64d9607bcd803bdd1f1) | [#227](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/227) |
| Remove tracked temporary PDFs | [ff34386](https://github.com/SE-FDA-NEU/G6_AI66A_SE/commit/ff3438619c718ce6ad06abc0f0b600280d858a57) | [#231](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/231) |
| Ignore rules, Git hooks, CI guard and guard tests | [1a9fccd](https://github.com/SE-FDA-NEU/G6_AI66A_SE/commit/1a9fccd836367263a91de2659613f54a6720b769) | [#234](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/234) |
| Case matrix, captured failure/pass output and agent guidance | [72f0257](https://github.com/SE-FDA-NEU/G6_AI66A_SE/commit/72f0257) | [#234](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/234) |

The handover branch is `chore/us04-us08-us09-test-handover`, based on `215_Extend_citation_to_reader_navigation_tests` (the head of PR #231). [Draft PR #234](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/234) is stacked on that branch to keep this review limited to hygiene and evidence. No PR was merged as part of this handover.
