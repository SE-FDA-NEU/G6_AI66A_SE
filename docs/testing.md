# Milestone 4 - Testing report

## 1. What we test, and why

| Layer | Tests | Purpose |
|---|---|---|
| Services (processing, extraction, validation and result schemas) | Pytest with controlled providers, fake clocks and real synthetic PDF extraction | Numeric accuracy, evidence, labels, search, retries and deadlines |
| Repository/data access (SQLAlchemy models and existing query modules) | Temporary SQLite with foreign keys and independent sessions | Persistence, ownership, relationships and rollback; no new repository abstraction |
| Routes (backend/app/api/) | In-process FastAPI TestClient | Authentication, input rejection, source access and persisted response content |
| Interface (frontend/tests/) | Playwright Chromium, Android 375 px and iOS 375 px checks | Navigation, rendering, responsive layout, visible progress/errors and reload behavior |

We test ownership and source evidence most heavily because leaks or falsely verified claims can mislead users. Numeric units, size limits and deadlines receive boundary cases because small comparison errors change business behavior. SQLite and controlled model responses make checks repeatable; they do not establish live-model latency.

## 2. Test cases for every P0 story

The table contains 70 distinct IDs covering all nine P0 stories. Every row maps to passing pytest nodes in [case-to-pytest.csv](evidence/m4/case-to-pytest.csv), including each concrete parametrized invocation. Source paths are relative to `backend/tests/`; IDs appear in test docstrings or parametrization IDs.

| ID | Story | Input | Expected result | Kind | Pytest source |
|---|---|---|---|---|---|
| TC-US01-01 | US01 | Five committed contracts, including a 0.05% daily penalty | Five exact rows with units and document/page evidence | normal | [test_financial_table.py](../backend/tests/test_financial_table.py#L28) |
| TC-US01-02 | US01 | Malformed JSON, missing fields or forged verification | Reject invalid output after bounded repair; publish no result | error | [test_gemini_analysis.py](../backend/tests/test_gemini_analysis.py#L98) |
| TC-US01-03 | US01 | Unknown, empty, mixed or wrong-field sources | Unsupported penalty stays unverified | error | [test_gemini_analysis.py](../backend/tests/test_gemini_analysis.py#L124) |
| TC-US01-04 | US01 | Batch finishes at 299.999 s, with/without retry | Five rows complete | boundary | [test_financial_table.py](../backend/tests/test_financial_table.py#L78) |
| TC-US01-05 | US01 | Batch reaches exactly 300 s, with/without retry | Reject late row five; retain earlier rows | boundary/error | [test_financial_table.py](../backend/tests/test_financial_table.py#L78) |
| TC-US01-06 | US01 | Batch reaches 300.001 s, with/without retry | Fail visibly; no verified late row | boundary/error | [test_financial_table.py](../backend/tests/test_financial_table.py#L78) |
| TC-US01-07 | US01 | Queue delay 300/300.001 s | Fail before calling the model | boundary/error | [test_financial_table.py](../backend/tests/test_financial_table.py#L133) |
| TC-US02-01 | US02 | 25 owned documents, 21 relevant; limits 7/20/100 | Return relevant owned hits across pages; 20 is not a maximum | normal/boundary | [test_cross_document_search.py](../backend/tests/test_cross_document_search.py#L87) |
| TC-US02-02 | US02 | Folder/label filters; page size 3, offsets 0/3/6/9 | Filter before pagination; foreign folders do not broaden results | normal/boundary | [test_cross_document_search.py](../backend/tests/test_cross_document_search.py#L120) |
| TC-US02-03 | US02 | Invalid queries/filters; query lengths 1/500/501, limits 0/1/100/101 | Accept valid boundaries; reject invalid input before embedding | error/boundary | [test_cross_document_search.py](../backend/tests/test_cross_document_search.py#L141) |
| TC-US02-04 | US02 | Forged owner_id and another account's matching documents | No foreign hits or source content | error | [test_cross_document_search.py](../backend/tests/test_cross_document_search.py#L166) |
| TC-US02-05 | US02 | Relevant results on physical page 3 | Exact snippets, offsets and reader references | normal | [test_search_index.py](../backend/tests/test_search_index.py#L23) |
| TC-US02-06 | US02 | Add owned document 26 | 22 relevant hits; old sources unchanged | boundary | [test_search_index.py](../backend/tests/test_search_index.py#L56) |
| TC-US02-07 | US02 | Deterministic semantic vectors for 21 relevant sources | All authorized sources remain searchable across page 20 | normal/boundary | [test_search_embeddings.py](../backend/tests/test_search_embeddings.py#L81) |
| TC-US02-08 | US02 | Excluded folders, labels and accounts | Filter sources before provider calls/cache writes | error | [test_search_embeddings.py](../backend/tests/test_search_embeddings.py#L131) |
| TC-US02-09 | US02 | Invalid embedding at index 0/49 in a 50-passage batch | 503 without partial cache; keyword search remains available | error/boundary | [test_search_embeddings.py](../backend/tests/test_search_embeddings.py#L158) |
| TC-US02-10 | US02 | Cached corpus grows to 26 owned documents | Embed only the two new passages; preserve old hits | boundary | [test_search_embeddings.py](../backend/tests/test_search_embeddings.py#L177) |
| TC-US03-01 | US03 | 15-page PDF with two supported actions | Persist grounded bullets, actions and citations | normal | [test_bullet_processing.py](../backend/tests/test_bullet_processing.py#L66) |
| TC-US03-02 | US03 | Source supports one action | Persist one action and explicit source limitation | normal/boundary | [test_bullet_processing.py](../backend/tests/test_bullet_processing.py#L66) |
| TC-US03-03 | US03 | Malformed bullet/action/type/source output | Reject output without publishing a summary | error | [test_bullet_processing.py](../backend/tests/test_bullet_processing.py#L147) |
| TC-US03-04 | US03 | 999 total words; one/two supported actions | Accept | boundary | [test_bullet_processing.py](../backend/tests/test_bullet_processing.py#L102) |
| TC-US03-05 | US03 | 1000 total words; one/two supported actions | Accept inclusive word limit | boundary | [test_bullet_processing.py](../backend/tests/test_bullet_processing.py#L102) |
| TC-US03-06 | US03 | 1001 total words; one/two supported actions | Reject; no saved result or citations | boundary/error | [test_bullet_processing.py](../backend/tests/test_bullet_processing.py#L102) |
| TC-US03-07 | US03 | Three actions in model output | Enforce the two-action output contract after bounded repair | boundary/error | [test_bullet_processing.py](../backend/tests/test_bullet_processing.py#L147) |
| TC-US03-08 | US03 | Source supports zero/one actions; model invents numeric advice | Remove unsupported advice and show limitation | error/boundary | [test_bullet_processing.py](../backend/tests/test_bullet_processing.py#L165) |
| TC-US03-09 | US03 | Finish at 179.999 s in analysis/persistence, with/without retry | Complete and persist | boundary | [test_bullet_processing.py](../backend/tests/test_bullet_processing.py#L216) |
| TC-US03-10 | US03 | Reach 180 s in analysis/persistence, with/without retry | Fail and roll back late output | boundary/error | [test_bullet_processing.py](../backend/tests/test_bullet_processing.py#L216) |
| TC-US03-11 | US03 | Reach 180.001 s in analysis/persistence, with/without retry | Fail and roll back late output | boundary/error | [test_bullet_processing.py](../backend/tests/test_bullet_processing.py#L216) |
| TC-US04-01 | US04 | Confidence 79%; assigned/unassigned folder; both review states | Low confidence; preserve folder and human metadata | boundary | [test_document_metadata_api.py](../backend/tests/test_document_metadata_api.py#L128) |
| TC-US04-02 | US04 | Confidence 80%; same folder/review variants | High confidence at the threshold; preserve human metadata | boundary | [test_document_metadata_api.py](../backend/tests/test_document_metadata_api.py#L128) |
| TC-US04-03 | US04 | Confidence 81%; same variants | High confidence without automatic folder movement | normal/boundary | [test_document_metadata_api.py](../backend/tests/test_document_metadata_api.py#L128) |
| TC-US04-04 | US04 | Empty AI label | Reject output; preserve previous metadata | error | [test_document_metadata_api.py](../backend/tests/test_document_metadata_api.py#L192) |
| TC-US04-10 | US04 | Two grounded concepts | Explicit limitation; no invented third concept | boundary | [test_concept_processing.py](../backend/tests/test_concept_processing.py#L78) |
| TC-US04-12 | US04 | Three grounded concepts | Accept lower concept-count boundary | boundary | [test_concept_processing.py](../backend/tests/test_concept_processing.py#L78) |
| TC-US04-14 | US04 | Five grounded concepts | Accept upper concept-count boundary | boundary | [test_concept_processing.py](../backend/tests/test_concept_processing.py#L78) |
| TC-US04-15 | US04 | Six concepts | Reject output | boundary/error | [test_concept_processing.py](../backend/tests/test_concept_processing.py#L158) |
| TC-US04-19 | US04 | Repeated keyword on known page 2 | Correct page and both match offsets | normal | [test_reader_extraction.py](../backend/tests/test_reader_extraction.py#L67) |
| TC-US04-20 | US04 | Match at start of page 1 | Correct first page/character | boundary | [test_reader_extraction.py](../backend/tests/test_reader_extraction.py#L67) |
| TC-US04-21 | US04 | Match at end of last page 3 | Correct last page/character | boundary | [test_reader_extraction.py](../backend/tests/test_reader_extraction.py#L67) |
| TC-US04-23 | US04 | Missing reader search query | 422 validation error, not an empty hit list | error | [test_reader_extraction.py](../backend/tests/test_reader_extraction.py#L113) |
| TC-US05-01 | US05 | Valid email or legacy username with password | 200; usable bearer/HttpOnly session | normal | [test_auth_authorization.py](../backend/tests/test_auth_authorization.py#L28) |
| TC-US05-02 | US05 | Wrong password or unknown account | 401; identical rejection and no session cookie | error | [test_auth_authorization.py](../backend/tests/test_auth_authorization.py#L51) |
| TC-US05-03 | US05 | Missing, forged or expired JWT on protected routes | 401; no protected data | error/boundary | [test_auth_authorization.py](../backend/tests/test_auth_authorization.py#L64) |
| TC-US05-04 | US05 | User B reads user A's document/file/pages/job/export | 403/404; no content leakage or retention changes | error | [test_auth_authorization.py](../backend/tests/test_auth_authorization.py#L92) |
| TC-US06-01 | US06 | PDF/DOCX/PPTX, mixed-case suffix and generic MIME | 202; accepted supported format | normal | [test_upload_validation.py](../backend/tests/test_upload_validation.py#L39) |
| TC-US06-02 | US06 | Five files, each exactly 5 MB | Accept five files, 25 MB total | boundary | [test_upload_validation.py](../backend/tests/test_upload_validation.py#L50) |
| TC-US06-03 | US06 | Unsupported suffix despite PDF MIME | 422; no stored job/files | error | [test_upload_validation.py](../backend/tests/test_upload_validation.py#L62) |
| TC-US06-04 | US06 | File size 5 MB + 1 byte | 422 file_too_large; no side effects | boundary/error | [test_upload_validation.py](../backend/tests/test_upload_validation.py#L70) |
| TC-US06-05 | US06 | Six files | 422 too_many_files; no saved batch | boundary/error | [test_upload_validation.py](../backend/tests/test_upload_validation.py#L78) |
| TC-US06-06 | US06 | Isolated invalid batch of 50 MB / 50 MB + 1 byte | Batch guard triggers only above 50 MB | boundary/error | [test_upload_validation.py](../backend/tests/test_upload_validation.py#L88) |
| TC-US06-07 | US06 | Four / five valid files | One queued job with matching file count | boundary | [test_upload_validation.py](../backend/tests/test_upload_validation.py#L166) |
| TC-US06-08 | US06 | File size 5 MB - 1 byte / exactly 5 MB | Accept both inclusive boundaries | boundary | [test_upload_validation.py](../backend/tests/test_upload_validation.py#L182) |
| TC-US06-09 | US06 | Zero-byte file alongside a valid file | 422; persist no upload artifacts | error/boundary | [test_upload_validation.py](../backend/tests/test_upload_validation.py#L193) |
| TC-US07-001 | US07 | Five files; pause the fourth processor | Processing with 3/5 complete; three saved results | normal | [test_job_lifecycle.py](../backend/tests/test_job_lifecycle.py#L110) |
| TC-US07-002 | US07 | Five successes; revisit and invoke processing again | Same saved results with no reprocessing | normal | [test_job_lifecycle.py](../backend/tests/test_job_lifecycle.py#L18) |
| TC-US07-003 | US07 | Processor times out on every attempt | Observable timeout; fail after three attempts; zero successes | error | [test_job_lifecycle.py](../backend/tests/test_job_lifecycle.py#L66) |
| TC-US07-004 | US07 | 33 s file timeout; retry finishes 0.001 s before job deadline | Complete within the remaining 7 s workflow budget | boundary | [test_processing_timeouts.py](../backend/tests/test_processing_timeouts.py#L78) |
| TC-US07-005 | US07 | Same retry finishes exactly at 180/300 s overall | Fail; discard late output and prevent later processing | boundary/error | [test_processing_timeouts.py](../backend/tests/test_processing_timeouts.py#L78) |
| TC-US07-006 | US07 | Same retry finishes 0.001 s after overall deadline | Fail without false success or saved output | boundary/error | [test_processing_timeouts.py](../backend/tests/test_processing_timeouts.py#L78) |
| TC-US07-007 | US07 | Worker crashes after one success in a three-file batch | Retain 1/3 result; fail unfinished files; hide private error | error | [test_upload_jobs.py](../backend/tests/test_upload_jobs.py#L245) |
| TC-US08-01 | US08 | Correct document/page evidence in bullet/table/concept output | Verified source reference preserved | normal | [test_evidence.py](../backend/tests/test_evidence.py#L75) |
| TC-US08-03 | US08 | Evidence points to invalid/textless source page | Reject evidence; mark claim Unverified without trusted link | error/boundary | [test_evidence.py](../backend/tests/test_evidence.py#L75) |
| TC-US08-04 | US08 | Two documents support the same claim | Persist separate document/page citations | normal | [test_evidence_persistence.py](../backend/tests/test_evidence_persistence.py#L68) |
| TC-US09-01 | US09 | Saved citation on physical page 2 | Open matching document/page with visible source highlight | normal | [test_reader_presentation.py](../backend/tests/test_reader_presentation.py#L21) |
| TC-US09-02 | US09 | Citation references an invalid source page | Remove invalid citation from saved reader summary | error | [test_reader_presentation.py](../backend/tests/test_reader_presentation.py#L60) |
| TC-US09-05 | US09 | First page on file/rendered-file endpoints | Serve correct readable source | boundary | [test_document_file.py](../backend/tests/test_document_file.py#L32) |
| TC-US09-06 | US09 | Last page on file/rendered-file endpoints | Serve correct readable source | boundary | [test_document_file.py](../backend/tests/test_document_file.py#L32) |
| TC-US09-07 | US09 | Page zero on both endpoints | 422; no file served | boundary/error | [test_document_file.py](../backend/tests/test_document_file.py#L53) |
| TC-US09-09 | US09 | Page beyond the last page | 422; no file served | boundary/error | [test_document_file.py](../backend/tests/test_document_file.py#L53) |
| TC-US09-12 | US09 | Image-only source page and fabricated highlight span | Page readable; reject nonexistent text span | normal/error | [test_document_file.py](../backend/tests/test_document_file.py#L72) |

MB means `1024 * 1024` bytes. Five valid 5 MB files total only 25 MB; TC-US06-06 tests the defensive 50 MB guard with invalid oversized files, not a valid full upload. Rejecting invalid evidence can mean removing a trusted link and marking a claim Unverified while the job still completes.

TC-US07-004/005/006 each run for a 180-second PDF bullet summary and a 300-second five-contract batch. Queue time leaves 40 seconds; the first 33-second timeout leaves only 7 seconds for retry. Fake-clock finish times 39.999/40/40.001 distinguish the workflow deadline from the per-attempt budget.

## 3. Automated tests

The assignment's `tests/` directory is `backend/tests/`. From `backend/`, after installing the development dependencies in [SETUP.md](SETUP.md):

```powershell
python -m pytest -v
```

Verification added reporting/temp options only: `-rs -p no:cacheprovider --basetemp=../../m4-pytest-final --junitxml=../../../docs/evidence/m4/backend-junit.xml`. No tests were deselected. A fresh clone at `34a86be` received the candidate patch, a new Python 3.12.14 virtualenv and dependencies installed from `requirements-dev.txt`; pytest used no `.env`, real database or live provider.

`conftest.py` supplies SQLite, temporary storage, dependency overrides and a recording queue. Processing tests inject controlled providers/processors. Extraction checks may launch cancellable subprocesses, but no application server is required. Fixtures are tracked or generated from tracked inputs.

| Check | Actual result | Evidence |
|---|---|---|
| Full fresh-clone pytest | 686 passed, 4 skipped, 0 failures | [Full named output](evidence/m4/pytest-clean-clone.txt), [JUnit](evidence/m4/backend-junit.xml) |
| Full Playwright | 213 passed, no retries | [Output](evidence/m4/playwright-full.txt) |
| Production frontend build | Passed | [Output](evidence/m4/frontend-build.txt) |
| App startup | Fresh local MySQL schema, 20-document seed, landing page, sign-in/session and document-list proxy passed | [Result](evidence/m4/application-startup.json) |
| Remote CI | Last inspected main run failed on mobile sidebar synchronization. A new remote run requires pushing the local fix. | [Run 41256271292](https://github.com/SE-FDA-NEU/G6_AI66A_SE/actions/runs/41256271292) |

![Full pytest output; zoom to read every test name](evidence/m4/pytest-full-output.png)

The startup check used and removed a new `documind_m4_check_*` schema; existing app data was untouched. Real-model timing and warning-free execution are not claimed. Dependency/datetime deprecation warnings remain visible in the output.

## 4. What the tests found

| Finding | Fix or deliberate mutation | Guard/evidence |
|---|---|---|
| Empty uploads were accepted | Merged fix rejects zero-byte files before saving jobs/files | TC-US06-09; [auth/upload handover](testing-auth-upload.md), PR #233 |
| Mobile CI waited on hidden folder controls | Replace a one-off visibility check with a wait for the mobile toggle and visible sidebar. No forced clicks or timeout increase. | All 213 browser checks pass; prior failure in CI run 41256271292 |
| Fake worker could publish partial JSON | First clean-clone run: 685 passed, four skipped, one JSONDecodeError. Production already writes atomically; the test child now stages/renames its progress file too. | `test_reported_page_count_tightens_extraction_deadline_before_text_finishes`; [first run](evidence/m4/pytest-first-run.txt), final run above |
| Retry-limit mutation | Set `processing.MAX_ATTEMPTS = 4` in memory; TC-US07-003 fails with `assert 4 == 3`; restore 3 in `finally` | [Red output](evidence/m4/us07-red.txt), [restored check](evidence/m4/us07-restored.txt); production files unchanged |
| Confidence mutation | Change `>= .8` to `> .8`; four exact-80% variants fail; restore original bytes | [US04/08/09 evidence](evidence/m4/us04-us08-us09-handover.md), merged PR #237 |
| Word-limit mutation | Change `> 1000` to `> 999`; exact-1000-word test fails; restore and rerun | [US01/02/03 evidence](../backend/test/T221-handover.txt), merged PR #240 |

Full team handovers remain available: [US05/06](testing-auth-upload.md), [US04/08/09](evidence/m4/us04-us08-us09-handover.md), and [US01/02/03 CSV](../backend/test/T221-case-matrix.csv). Historical failed/flaky runs are retained and are not relabeled as new passes.
