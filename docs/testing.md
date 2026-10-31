# US04 / US08 / US09 pytest case matrix and execution evidence

Evidence captured on 31 October 2026 (Asia/Bangkok), Windows, Python 3.12.6 and pytest 9.1.1, against main commit `b18793e679b9557927b6a248e6c3e2b67dddd7ca`. This is a fresh collection, deliberate mutation and restored-code run. The final diff changes only `docs/testing.md`; existing tests and application code remain unchanged.

The acceptance criteria are in [requirements.md](requirements.md). Tests use isolated SQLite, generated PDFs and injected analyzers. The complete matrix maps **80 unique TC IDs to 102 parametrized pytest invocations**, with normal, rejection and applicable boundary coverage for every story.

## Coverage summary

| Story | Case IDs | Unique IDs | Pytest invocations | Coverage |
|---|---|---:|---:|---|
| US04 | TC-US04-01 through TC-US04-56 | 56 | 65 | Label confidence, unchanged human metadata/folder, concept validation, search, physical page navigation and PDF highlights. |
| US08 | TC-US08-01 through TC-US08-11 | 11 | 17 | Valid/missing/invalid evidence across bullet/table/concept modes, distinct document citations, persisted invalid/stale/mixed sources. |
| US09 | TC-US09-01 through TC-US09-13 | 13 | 20 | Exact citation source/highlight, invalid citations, first/last page, invalid page input, textless source fallback. |

At least three scenarios per story are explicitly identified here; every collected invocation is mapped in the complete matrix below.

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


US04-01/02/03 each expand into four combinations: assigned/unassigned folder x confirmed/needs_review. US08-01/02/03 each run in bullet, table and concept modes. US09-05 through US09-11 each run on both `file` and `rendered-file` endpoints. For evidence, rejection means removing an untrusted source and persisting Unverified; it does not necessarily mean an HTTP error or a failed job.

## Complete case-to-test/input matrix

Each row names the existing test and all parametrized inputs for one actual invocation. Tests are linked to their source files. Expected outcomes summarize assertions in those tests.

| Case ID | Scenario | Test node and inputs | Expected outcome |
|---|---|---|---|
| TC-US04-01 | Normal / boundary | [test_document_metadata_api.py::test_confidence_threshold_values_persisted](../backend/tests/test_document_metadata_api.py)<br>`{"assigned_folder": true, "review_state": "confirmed", "confidence": 0.79, "confidence_level": "low"}` | Job completes; persisted confidence level matches threshold; folder, human label and review state stay unchanged. |
| TC-US04-01 | Normal / boundary | [test_document_metadata_api.py::test_confidence_threshold_values_persisted](../backend/tests/test_document_metadata_api.py)<br>`{"assigned_folder": true, "review_state": "needs_review", "confidence": 0.79, "confidence_level": "low"}` | Job completes; persisted confidence level matches threshold; folder, human label and review state stay unchanged. |
| TC-US04-01 | Normal / boundary | [test_document_metadata_api.py::test_confidence_threshold_values_persisted](../backend/tests/test_document_metadata_api.py)<br>`{"assigned_folder": false, "review_state": "confirmed", "confidence": 0.79, "confidence_level": "low"}` | Job completes; persisted confidence level matches threshold; folder, human label and review state stay unchanged. |
| TC-US04-01 | Normal / boundary | [test_document_metadata_api.py::test_confidence_threshold_values_persisted](../backend/tests/test_document_metadata_api.py)<br>`{"assigned_folder": false, "review_state": "needs_review", "confidence": 0.79, "confidence_level": "low"}` | Job completes; persisted confidence level matches threshold; folder, human label and review state stay unchanged. |
| TC-US04-02 | Normal / boundary | [test_document_metadata_api.py::test_confidence_threshold_values_persisted](../backend/tests/test_document_metadata_api.py)<br>`{"assigned_folder": true, "review_state": "confirmed", "confidence": 0.8, "confidence_level": "high"}` | Job completes; persisted confidence level matches threshold; folder, human label and review state stay unchanged. |
| TC-US04-02 | Normal / boundary | [test_document_metadata_api.py::test_confidence_threshold_values_persisted](../backend/tests/test_document_metadata_api.py)<br>`{"assigned_folder": true, "review_state": "needs_review", "confidence": 0.8, "confidence_level": "high"}` | Job completes; persisted confidence level matches threshold; folder, human label and review state stay unchanged. |
| TC-US04-02 | Normal / boundary | [test_document_metadata_api.py::test_confidence_threshold_values_persisted](../backend/tests/test_document_metadata_api.py)<br>`{"assigned_folder": false, "review_state": "confirmed", "confidence": 0.8, "confidence_level": "high"}` | Job completes; persisted confidence level matches threshold; folder, human label and review state stay unchanged. |
| TC-US04-02 | Normal / boundary | [test_document_metadata_api.py::test_confidence_threshold_values_persisted](../backend/tests/test_document_metadata_api.py)<br>`{"assigned_folder": false, "review_state": "needs_review", "confidence": 0.8, "confidence_level": "high"}` | Job completes; persisted confidence level matches threshold; folder, human label and review state stay unchanged. |
| TC-US04-03 | Normal / boundary | [test_document_metadata_api.py::test_confidence_threshold_values_persisted](../backend/tests/test_document_metadata_api.py)<br>`{"assigned_folder": true, "review_state": "confirmed", "confidence": 0.81, "confidence_level": "high"}` | Job completes; persisted confidence level matches threshold; folder, human label and review state stay unchanged. |
| TC-US04-03 | Normal / boundary | [test_document_metadata_api.py::test_confidence_threshold_values_persisted](../backend/tests/test_document_metadata_api.py)<br>`{"assigned_folder": true, "review_state": "needs_review", "confidence": 0.81, "confidence_level": "high"}` | Job completes; persisted confidence level matches threshold; folder, human label and review state stay unchanged. |
| TC-US04-03 | Normal / boundary | [test_document_metadata_api.py::test_confidence_threshold_values_persisted](../backend/tests/test_document_metadata_api.py)<br>`{"assigned_folder": false, "review_state": "confirmed", "confidence": 0.81, "confidence_level": "high"}` | Job completes; persisted confidence level matches threshold; folder, human label and review state stay unchanged. |
| TC-US04-03 | Normal / boundary | [test_document_metadata_api.py::test_confidence_threshold_values_persisted](../backend/tests/test_document_metadata_api.py)<br>`{"assigned_folder": false, "review_state": "needs_review", "confidence": 0.81, "confidence_level": "high"}` | Job completes; persisted confidence level matches threshold; folder, human label and review state stay unchanged. |
| TC-US04-04 | Rejection | [test_document_metadata_api.py::test_invalid_mocked_label_is_not_published](../backend/tests/test_document_metadata_api.py)<br>`{"label": {"ai_label": "", "ai_confidence": 0.8}}` | Job/file fails with invalid_result; previous metadata and folder survive. |
| TC-US04-05 | Rejection / boundary | [test_document_metadata_api.py::test_invalid_mocked_label_is_not_published](../backend/tests/test_document_metadata_api.py)<br>`{"label": {"ai_label": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "ai_confidence": 0.8}}` | Job/file fails with invalid_result; previous metadata and folder survive. |
| TC-US04-06 | Rejection | [test_document_metadata_api.py::test_invalid_mocked_label_is_not_published](../backend/tests/test_document_metadata_api.py)<br>`{"label": {"ai_label": "Fixed AI label"}}` | Job/file fails with invalid_result; previous metadata and folder survive. |
| TC-US04-07 | Rejection | [test_document_metadata_api.py::test_invalid_mocked_label_is_not_published](../backend/tests/test_document_metadata_api.py)<br>`{"label": {"ai_confidence": 0.8}}` | Job/file fails with invalid_result; previous metadata and folder survive. |
| TC-US04-08 | Rejection / boundary | [test_document_metadata_api.py::test_invalid_mocked_label_is_not_published](../backend/tests/test_document_metadata_api.py)<br>`{"label": {"ai_label": "Fixed AI label", "ai_confidence": -0.01}}` | Job/file fails with invalid_result; previous metadata and folder survive. |
| TC-US04-09 | Rejection / boundary | [test_document_metadata_api.py::test_invalid_mocked_label_is_not_published](../backend/tests/test_document_metadata_api.py)<br>`{"label": {"ai_label": "Fixed AI label", "ai_confidence": 1.01}}` | Job/file fails with invalid_result; previous metadata and folder survive. |
| TC-US04-10 | Normal / boundary | [test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence](../backend/tests/test_concept_processing.py)<br>`{"concept_count": 2, "limitation": null}` | Grounded concepts persist; two-concept output includes explicit/generated limitation. |
| TC-US04-11 | Normal / boundary | [test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence](../backend/tests/test_concept_processing.py)<br>`{"concept_count": 2, "limitation": "The source supports only two core concepts."}` | Grounded concepts persist; two-concept output includes explicit/generated limitation. |
| TC-US04-12 | Normal / boundary | [test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence](../backend/tests/test_concept_processing.py)<br>`{"concept_count": 3, "limitation": null}` | Grounded concepts persist; two-concept output includes explicit/generated limitation. |
| TC-US04-13 | Normal | [test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence](../backend/tests/test_concept_processing.py)<br>`{"concept_count": 4, "limitation": null}` | Grounded concepts persist; two-concept output includes explicit/generated limitation. |
| TC-US04-14 | Normal / boundary | [test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence](../backend/tests/test_concept_processing.py)<br>`{"concept_count": 5, "limitation": null}` | Grounded concepts persist; two-concept output includes explicit/generated limitation. |
| TC-US04-15 | Rejection / boundary | [test_concept_processing.py::test_more_than_five_concepts_rejected_by_shared_contract](../backend/tests/test_concept_processing.py)<br>`{"concept_count": 6}` | Six concepts rejected by shared result validation. |
| TC-US04-16 | Rejection | [test_concept_processing.py::test_invalid_mocked_concepts_are_not_published](../backend/tests/test_concept_processing.py)<br>`{"concept": {"name": "", "description": {"text": "Fixed description"}}}` | Malformed concept output is rejected and not published. |
| TC-US04-17 | Rejection | [test_concept_processing.py::test_invalid_mocked_concepts_are_not_published](../backend/tests/test_concept_processing.py)<br>`{"concept": {"name": "Monetary Policy"}}` | Malformed concept output is rejected and not published. |
| TC-US04-18 | Rejection | [test_concept_processing.py::test_invalid_mocked_concepts_are_not_published](../backend/tests/test_concept_processing.py)<br>`{"concept": {"name": "Monetary Policy", "description": {"text": ""}}}` | Malformed concept output is rejected and not published. |
| TC-US04-19 | Normal | [test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions](../backend/tests/test_reader_extraction.py)<br>`{"query": "keyword", "page_number": 2, "spans": [[7, 14], [15, 22]]}` | 200; correct document/page, source offsets, version and highlight URL. |
| TC-US04-20 | Normal / boundary | [test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions](../backend/tests/test_reader_extraction.py)<br>`{"query": "Alpha", "page_number": 1, "spans": [[0, 5]]}` | 200; correct document/page, source offsets, version and highlight URL. |
| TC-US04-21 | Normal / boundary | [test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions](../backend/tests/test_reader_extraction.py)<br>`{"query": "Omega", "page_number": 3, "spans": [[10, 15]]}` | 200; correct document/page, source offsets, version and highlight URL. |
| TC-US04-22 | Normal / boundary | [test_reader_extraction.py::test_reader_search_no_match_is_a_valid_empty_result](../backend/tests/test_reader_extraction.py)<br>`{"query": "absentword"}` | 200; zero hits and an empty hit list. |
| TC-US04-23 | Rejection | [test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result](../backend/tests/test_reader_extraction.py)<br>`{"params": {}, "error_location": ["query", "q"]}` | 422 with validation details; no hit payload. |
| TC-US04-24 | Rejection / boundary | [test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result](../backend/tests/test_reader_extraction.py)<br>`{"params": {"q": ""}, "error_location": ["query", "q"]}` | 422 with validation details; no hit payload. |
| TC-US04-25 | Rejection / boundary | [test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result](../backend/tests/test_reader_extraction.py)<br>`{"params": {"q": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}, "error_location": ["query", "q"]}` | 422 with validation details; no hit payload. |
| TC-US04-26 | Rejection | [test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result](../backend/tests/test_reader_extraction.py)<br>`{"params": {"q": " \t\n"}, "error_location": null}` | 422 with validation details; no hit payload. |
| TC-US04-27 | Rejection | [test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result](../backend/tests/test_reader_extraction.py)<br>`{"params": {"q": "!!!"}, "error_location": null}` | 422 with validation details; no hit payload. |
| TC-US04-28 | Normal / boundary | [test_reader_extraction.py::test_reader_page_text_preserves_physical_page_and_positions](../backend/tests/test_reader_extraction.py)<br>`{"page_number": 1, "expected_text": "Alpha first page."}` | 200; exact physical page text and glyph positions. |
| TC-US04-29 | Normal | [test_reader_extraction.py::test_reader_page_text_preserves_physical_page_and_positions](../backend/tests/test_reader_extraction.py)<br>`{"page_number": 2, "expected_text": "Middle keyword keyword."}` | 200; exact physical page text and glyph positions. |
| TC-US04-30 | Normal / boundary | [test_reader_extraction.py::test_reader_page_text_preserves_physical_page_and_positions](../backend/tests/test_reader_extraction.py)<br>`{"page_number": 3, "expected_text": "Last page Omega"}` | 200; exact physical page text and glyph positions. |
| TC-US04-31 | Rejection / boundary | [test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages](../backend/tests/test_reader_extraction.py)<br>`{"page_input": "0", "status": 404, "detail": "Page not found"}` | 404 for nonexistent physical page; 422 for noninteger input; no source text returned. |
| TC-US04-32 | Rejection / boundary | [test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages](../backend/tests/test_reader_extraction.py)<br>`{"page_input": "-1", "status": 404, "detail": "Page not found"}` | 404 for nonexistent physical page; 422 for noninteger input; no source text returned. |
| TC-US04-33 | Rejection / boundary | [test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages](../backend/tests/test_reader_extraction.py)<br>`{"page_input": "4", "status": 404, "detail": "Page not found"}` | 404 for nonexistent physical page; 422 for noninteger input; no source text returned. |
| TC-US04-34 | Rejection | [test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages](../backend/tests/test_reader_extraction.py)<br>`{"page_input": "invalid", "status": 422, "detail": null}` | 404 for nonexistent physical page; 422 for noninteger input; no source text returned. |
| TC-US04-35 | Rejection | [test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages](../backend/tests/test_reader_extraction.py)<br>`{"page_input": "1.5", "status": 422, "detail": null}` | 404 for nonexistent physical page; 422 for noninteger input; no source text returned. |
| TC-US04-36 | Normal | [test_reader_presentation.py::test_keyword_highlight_draws_only_at_known_match_positions](../backend/tests/test_reader_presentation.py)<br>`{"page_number": 2, "query": "KEYWORD", "spans": [[7, 14], [15, 22]]}` | 200; highlight rectangles match source spans, only on target page; original bytes unchanged. |
| TC-US04-37 | Normal / boundary | [test_reader_presentation.py::test_keyword_highlight_draws_only_at_known_match_positions](../backend/tests/test_reader_presentation.py)<br>`{"page_number": 1, "query": "Alpha", "spans": [[0, 5]]}` | 200; highlight rectangles match source spans, only on target page; original bytes unchanged. |
| TC-US04-38 | Normal / boundary | [test_reader_presentation.py::test_keyword_highlight_draws_only_at_known_match_positions](../backend/tests/test_reader_presentation.py)<br>`{"page_number": 3, "query": "Omega", "spans": [[10, 15]]}` | 200; highlight rectangles match source spans, only on target page; original bytes unchanged. |
| TC-US04-39 | Normal / boundary | [test_reader_presentation.py::test_valid_query_without_highlights_returns_readable_pdf](../backend/tests/test_reader_presentation.py)<br>`{"query": "absentword"}` | 200; readable PDF with no highlight marks; original source unchanged. |
| TC-US04-40 | Normal / boundary | [test_reader_presentation.py::test_valid_query_without_highlights_returns_readable_pdf](../backend/tests/test_reader_presentation.py)<br>`{"query": ""}` | 200; readable PDF with no highlight marks; original source unchanged. |
| TC-US04-41 | Rejection / boundary | [test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf](../backend/tests/test_reader_presentation.py)<br>`{"params": {"highlight_page": 2, "q": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}, "error_field": "q", "detail": null}` | 422 with expected validation field/detail; original source unchanged. |
| TC-US04-42 | Rejection / boundary | [test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf](../backend/tests/test_reader_presentation.py)<br>`{"params": {"highlight_page": 0, "q": "keyword"}, "error_field": "highlight_page", "detail": null}` | 422 with expected validation field/detail; original source unchanged. |
| TC-US04-43 | Rejection / boundary | [test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf](../backend/tests/test_reader_presentation.py)<br>`{"params": {"highlight_page": -1, "q": "keyword"}, "error_field": "highlight_page", "detail": null}` | 422 with expected validation field/detail; original source unchanged. |
| TC-US04-44 | Rejection / boundary | [test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf](../backend/tests/test_reader_presentation.py)<br>`{"params": {"highlight_page": 4, "q": "keyword"}, "error_field": null, "detail": "Highlight page is outside the document."}` | 422 with expected validation field/detail; original source unchanged. |
| TC-US04-45 | Rejection | [test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf](../backend/tests/test_reader_presentation.py)<br>`{"params": {"highlight_page": "invalid", "q": "keyword"}, "error_field": "highlight_page", "detail": null}` | 422 with expected validation field/detail; original source unchanged. |
| TC-US04-46 | Rejection | [test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf](../backend/tests/test_reader_presentation.py)<br>`{"params": {"highlight_page": "1.5", "q": "keyword"}, "error_field": "highlight_page", "detail": null}` | 422 with expected validation field/detail; original source unchanged. |
| TC-US04-47 | Rejection | [test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf](../backend/tests/test_reader_presentation.py)<br>`{"params": {"q": "keyword"}, "error_field": null, "detail": "A highlight page is required."}` | 422 with expected validation field/detail; original source unchanged. |
| TC-US04-48 | Rejection / boundary | [test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf](../backend/tests/test_reader_presentation.py)<br>`{"params": {"highlight_page": 1, "start": -1, "end": 5}, "error_field": "start", "detail": null}` | 422 with expected validation field/detail; original source unchanged. |
| TC-US04-49 | Rejection / boundary | [test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf](../backend/tests/test_reader_presentation.py)<br>`{"params": {"highlight_page": 3, "start": 10, "end": 16}, "error_field": null, "detail": "Highlight span is outside the page text."}` | 422 with expected validation field/detail; original source unchanged. |
| TC-US04-50 | Rejection / boundary | [test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf](../backend/tests/test_reader_presentation.py)<br>`{"params": {"highlight_page": 3, "start": 15, "end": 16}, "error_field": null, "detail": "Highlight span is outside the page text."}` | 422 with expected validation field/detail; original source unchanged. |
| TC-US04-51 | Rejection / boundary | [test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf](../backend/tests/test_reader_presentation.py)<br>`{"params": {"highlight_page": 2, "start": 7, "end": 7}, "error_field": null, "detail": "Highlight span is outside the page text."}` | 422 with expected validation field/detail; original source unchanged. |
| TC-US04-52 | Rejection / boundary | [test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf](../backend/tests/test_reader_presentation.py)<br>`{"params": {"highlight_page": 2, "start": 14, "end": 7}, "error_field": null, "detail": "Highlight span is outside the page text."}` | 422 with expected validation field/detail; original source unchanged. |
| TC-US04-53 | Rejection | [test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf](../backend/tests/test_reader_presentation.py)<br>`{"params": {"highlight_page": 2, "start": 7}, "error_field": null, "detail": "Highlight span is outside the page text."}` | 422 with expected validation field/detail; original source unchanged. |
| TC-US04-54 | Rejection | [test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf](../backend/tests/test_reader_presentation.py)<br>`{"params": {"highlight_page": 2, "end": 14}, "error_field": null, "detail": "Highlight requires both start and end."}` | 422 with expected validation field/detail; original source unchanged. |
| TC-US04-55 | Normal / boundary | [test_reader_presentation.py::test_exact_match_span_accepts_first_and_last_character_boundaries](../backend/tests/test_reader_presentation.py)<br>`{"page_number": 1, "start": 0, "end": 5, "query": "Alpha"}` | 200; valid span at start/end draws only expected highlight; source unchanged. |
| TC-US04-56 | Normal / boundary | [test_reader_presentation.py::test_exact_match_span_accepts_first_and_last_character_boundaries](../backend/tests/test_reader_presentation.py)<br>`{"page_number": 3, "start": 10, "end": 15, "query": "Omega"}` | 200; valid span at start/end draws only expected highlight; source unchanged. |
| TC-US08-01 | Normal | [test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode](../backend/tests/test_evidence.py)<br>`{"state": "valid", "mode": "bullet"}` | Valid source persists with correct document/page; missing/invalid source becomes Unverified, with no trusted page link, in every mode. |
| TC-US08-01 | Normal | [test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode](../backend/tests/test_evidence.py)<br>`{"state": "valid", "mode": "concept"}` | Valid source persists with correct document/page; missing/invalid source becomes Unverified, with no trusted page link, in every mode. |
| TC-US08-01 | Normal | [test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode](../backend/tests/test_evidence.py)<br>`{"state": "valid", "mode": "table"}` | Valid source persists with correct document/page; missing/invalid source becomes Unverified, with no trusted page link, in every mode. |
| TC-US08-02 | Rejection | [test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode](../backend/tests/test_evidence.py)<br>`{"state": "missing", "mode": "bullet"}` | Valid source persists with correct document/page; missing/invalid source becomes Unverified, with no trusted page link, in every mode. |
| TC-US08-02 | Rejection | [test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode](../backend/tests/test_evidence.py)<br>`{"state": "missing", "mode": "concept"}` | Valid source persists with correct document/page; missing/invalid source becomes Unverified, with no trusted page link, in every mode. |
| TC-US08-02 | Rejection | [test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode](../backend/tests/test_evidence.py)<br>`{"state": "missing", "mode": "table"}` | Valid source persists with correct document/page; missing/invalid source becomes Unverified, with no trusted page link, in every mode. |
| TC-US08-03 | Rejection / boundary | [test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode](../backend/tests/test_evidence.py)<br>`{"state": "invalid", "mode": "bullet"}` | Valid source persists with correct document/page; missing/invalid source becomes Unverified, with no trusted page link, in every mode. |
| TC-US08-03 | Rejection / boundary | [test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode](../backend/tests/test_evidence.py)<br>`{"state": "invalid", "mode": "concept"}` | Valid source persists with correct document/page; missing/invalid source becomes Unverified, with no trusted page link, in every mode. |
| TC-US08-03 | Rejection / boundary | [test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode](../backend/tests/test_evidence.py)<br>`{"state": "invalid", "mode": "table"}` | Valid source persists with correct document/page; missing/invalid source becomes Unverified, with no trusted page link, in every mode. |
| TC-US08-04 | Normal | [test_evidence_persistence.py::test_two_documents_supporting_one_bullet_claim_persist_distinct_citations](../backend/tests/test_evidence_persistence.py)<br>`{"second_page": 1}` | Two citations retain distinct document IDs/names and exact pages in API, DB and reloaded result. |
| TC-US08-05 | Normal / boundary | [test_evidence_persistence.py::test_two_documents_supporting_one_bullet_claim_persist_distinct_citations](../backend/tests/test_evidence_persistence.py)<br>`{"second_page": 3}` | Two citations retain distinct document IDs/names and exact pages in API, DB and reloaded result. |
| TC-US08-06 | Rejection | [test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links](../backend/tests/test_evidence_persistence.py)<br>`{"source_state": "missing"}` | Unverified status/issues persist; invalid links removed; mixed input retains only valid evidence. |
| TC-US08-07 | Rejection | [test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links](../backend/tests/test_evidence_persistence.py)<br>`{"source_state": "unknown_document"}` | Unverified status/issues persist; invalid links removed; mixed input retains only valid evidence. |
| TC-US08-08 | Rejection | [test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links](../backend/tests/test_evidence_persistence.py)<br>`{"source_state": "wrong_page"}` | Unverified status/issues persist; invalid links removed; mixed input retains only valid evidence. |
| TC-US08-09 | Rejection | [test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links](../backend/tests/test_evidence_persistence.py)<br>`{"source_state": "wrong_quote"}` | Unverified status/issues persist; invalid links removed; mixed input retains only valid evidence. |
| TC-US08-10 | Rejection | [test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links](../backend/tests/test_evidence_persistence.py)<br>`{"source_state": "wrong_version"}` | Unverified status/issues persist; invalid links removed; mixed input retains only valid evidence. |
| TC-US08-11 | Rejection / boundary | [test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links](../backend/tests/test_evidence_persistence.py)<br>`{"source_state": "mixed"}` | Unverified status/issues persist; invalid links removed; mixed input retains only valid evidence. |
| TC-US09-01 | Normal | [test_reader_presentation.py::test_saved_citation_opens_matching_document_page_and_visible_highlight](../backend/tests/test_reader_presentation.py)<br>`{"source_page": 2}` | 200; same saved job/document, exact cited page; visible PDF highlight appears only on that page. |
| TC-US09-02 | Rejection | [test_reader_presentation.py::test_invalid_citation_is_removed_from_saved_reader_summary](../backend/tests/test_reader_presentation.py)<br>`{"invalid_source": "page"}` | Claim remains Unverified; invalid source removed from persisted summary. |
| TC-US09-03 | Rejection | [test_reader_presentation.py::test_invalid_citation_is_removed_from_saved_reader_summary](../backend/tests/test_reader_presentation.py)<br>`{"invalid_source": "document"}` | Claim remains Unverified; invalid source removed from persisted summary. |
| TC-US09-04 | Rejection | [test_reader_presentation.py::test_invalid_citation_is_removed_from_saved_reader_summary](../backend/tests/test_reader_presentation.py)<br>`{"invalid_source": "version"}` | Claim remains Unverified; invalid source removed from persisted summary. |
| TC-US09-05 | Normal / boundary | [test_document_file.py::test_citation_page_selects_readable_original_without_changing_source](../backend/tests/test_document_file.py)<br>`{"page": 1, "endpoint": "file"}` | 200 PDF; X-Initial-Page equals requested first/last page; exact original bytes. |
| TC-US09-05 | Normal / boundary | [test_document_file.py::test_citation_page_selects_readable_original_without_changing_source](../backend/tests/test_document_file.py)<br>`{"page": 1, "endpoint": "rendered-file"}` | 200 PDF; X-Initial-Page equals requested first/last page; exact original bytes. |
| TC-US09-06 | Normal / boundary | [test_document_file.py::test_citation_page_selects_readable_original_without_changing_source](../backend/tests/test_document_file.py)<br>`{"page": 3, "endpoint": "file"}` | 200 PDF; X-Initial-Page equals requested first/last page; exact original bytes. |
| TC-US09-06 | Normal / boundary | [test_document_file.py::test_citation_page_selects_readable_original_without_changing_source](../backend/tests/test_document_file.py)<br>`{"page": 3, "endpoint": "rendered-file"}` | 200 PDF; X-Initial-Page equals requested first/last page; exact original bytes. |
| TC-US09-07 | Rejection / boundary | [test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file](../backend/tests/test_document_file.py)<br>`{"page": "0", "detail": "Page must be greater than or equal to 1", "endpoint": "file"}` | 422; expected page validation detail; no PDF served. |
| TC-US09-07 | Rejection / boundary | [test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file](../backend/tests/test_document_file.py)<br>`{"page": "0", "detail": "Page must be greater than or equal to 1", "endpoint": "rendered-file"}` | 422; expected page validation detail; no PDF served. |
| TC-US09-08 | Rejection / boundary | [test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file](../backend/tests/test_document_file.py)<br>`{"page": "-1", "detail": "Page must be greater than or equal to 1", "endpoint": "file"}` | 422; expected page validation detail; no PDF served. |
| TC-US09-08 | Rejection / boundary | [test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file](../backend/tests/test_document_file.py)<br>`{"page": "-1", "detail": "Page must be greater than or equal to 1", "endpoint": "rendered-file"}` | 422; expected page validation detail; no PDF served. |
| TC-US09-09 | Rejection / boundary | [test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file](../backend/tests/test_document_file.py)<br>`{"page": "4", "detail": "Page outside document", "endpoint": "file"}` | 422; expected page validation detail; no PDF served. |
| TC-US09-09 | Rejection / boundary | [test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file](../backend/tests/test_document_file.py)<br>`{"page": "4", "detail": "Page outside document", "endpoint": "rendered-file"}` | 422; expected page validation detail; no PDF served. |
| TC-US09-10 | Rejection | [test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file](../backend/tests/test_document_file.py)<br>`{"page": "invalid", "detail": null, "endpoint": "file"}` | 422; expected page validation detail; no PDF served. |
| TC-US09-10 | Rejection | [test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file](../backend/tests/test_document_file.py)<br>`{"page": "invalid", "detail": null, "endpoint": "rendered-file"}` | 422; expected page validation detail; no PDF served. |
| TC-US09-11 | Rejection | [test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file](../backend/tests/test_document_file.py)<br>`{"page": "1.5", "detail": null, "endpoint": "file"}` | 422; expected page validation detail; no PDF served. |
| TC-US09-11 | Rejection | [test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file](../backend/tests/test_document_file.py)<br>`{"page": "1.5", "detail": null, "endpoint": "rendered-file"}` | 422; expected page validation detail; no PDF served. |
| TC-US09-12 | Normal / boundary | [test_document_file.py::test_textless_page_remains_readable_but_cannot_accept_citation_span](../backend/tests/test_document_file.py)<br>`{"content": "b'q 100 0 0 100 72 600 cm /Im0 Do Q'"}` | 200 for original page with no text; fabricated highlight span rejected with 422. |
| TC-US09-13 | Normal / boundary | [test_document_file.py::test_textless_page_remains_readable_but_cannot_accept_citation_span](../backend/tests/test_document_file.py)<br>`{"content": "b''"}` | 200 for original page with no text; fabricated highlight span rejected with 422. |

## Commands

Run from the repository root after installing `backend/requirements-dev.txt`. On Linux, substitute the activated environment's `python` for the Windows interpreter path. Fresh pytest working directories are under system temp, outside the checkout.

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

# Inspect the same collected story selection.
& $py -m pytest @storyTests -k 'TC-US04 or TC-US08 or TC-US09' --collect-only -q -p no:cacheprovider

# Run all cases after restoring the correct comparison.
$runTemp = Join-Path ([IO.Path]::GetTempPath()) ('documind-' + [guid]::NewGuid())
& $py -m pytest @storyTests -k 'TC-US04 or TC-US08 or TC-US09' -vv --tb=short -p no:cacheprovider --basetemp $runTemp
```

## Deliberately broken rule and restoration

The tested rule is that confidence **0.80 is high**. The experiment temporarily changed only the comparison in [result_persistence.py](../backend/app/services/result_persistence.py):

```diff
- 'high' if document.ai_confidence >= .8 else 'low'
+ 'high' if document.ai_confidence > .8 else 'low'
```

With that deliberate defect present, the actual command selected all four `TC-US04-02` folder/review variants:

```powershell
$mutationTemp = Join-Path ([IO.Path]::GetTempPath()) ('documind-mutation-' + [guid]::NewGuid())
& $py -m pytest backend/tests/test_document_metadata_api.py -k TC-US04-02 -vv --tb=short -p no:cacheprovider --basetemp $mutationTemp
```

Each failed because the application returned `confidence_level='low'` instead of `'high'`. The capture restored the original source bytes in a `finally` block before running the complete passing selection. The deliberate defect was never committed. Before/after SHA-256: `ee6f5aa1e6bc11bc6f09b03be8de9e9b5d0996a820de2ea854cf0459b316af31`.

Actual captured results:

| Run | Result | Exit code |
|---|---|---:|
| Collection | 102/172 tests collected; 70 deselected | 0 |
| Broken rule | 4 failed, 17 deselected, 27 warnings in 8.76s | 1 |
| First restored run, temp-file permission failure | 1 failed, 101 passed, 70 deselected, 714 warnings in 51.52s | 1 |
| Correct code restored, full retry outside sandbox | 102 passed, 70 deselected, 714 warnings in 53.66s | 0 |

The complete outputs follow. Line endings and trailing whitespace were normalized for Markdown; assertion text, results and exit codes are preserved. Absolute system-temp paths in the captured commands identify the original run and need not be reused.

The collection command used a temporary pytest reporter outside the checkout to export `callspec.params` for comparison with the matrix. All 102 matrix rows matched the freshly collected function names and parameter values. The collection command in the Commands section reproduces the same test selection without that reporter.

The first restored-code run returned 101 passes and one failure: reading a temporary `page_count.json` raised `PermissionError`, so TC-US04-08 reported the generic processing error rather than `invalid_result`. No application/test code was changed to handle this. The full selection was rerun outside the sandbox with a fresh system-temp directory. The passing capture below is that rerun; the intermediate failure is also preserved for transparency. A retry whose test output could not be saved because of cross-context temp permissions is not used as passing evidence.

### Actual collection output

```text
$ D:\SE_AI66A\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_document_metadata_api.py backend/tests/test_concept_processing.py backend/tests/test_reader_extraction.py backend/tests/test_reader_presentation.py backend/tests/test_evidence.py backend/tests/test_evidence_persistence.py backend/tests/test_document_file.py -k "TC-US04 or TC-US08 or TC-US09" --collect-only -q -p no:cacheprovider -p story_capture
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-confirmed-TC-US04-01-below-80]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-confirmed-TC-US04-02-at-80]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-confirmed-TC-US04-03-above-80]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-needs_review-TC-US04-01-below-80]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-needs_review-TC-US04-02-at-80]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-needs_review-TC-US04-03-above-80]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-confirmed-TC-US04-01-below-80]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-confirmed-TC-US04-02-at-80]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-confirmed-TC-US04-03-above-80]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-needs_review-TC-US04-01-below-80]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-needs_review-TC-US04-02-at-80]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-needs_review-TC-US04-03-above-80]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-04-empty-label]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-05-long-label]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-06-missing-confidence]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-07-missing-label]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-08-negative-confidence]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-09-confidence-over-100]
backend/tests/test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence[TC-US04-10-two-concepts-generated-limitation]
backend/tests/test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence[TC-US04-11-two-concepts-explicit-limitation]
backend/tests/test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence[TC-US04-12-three-concepts]
backend/tests/test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence[TC-US04-13-four-concepts]
backend/tests/test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence[TC-US04-14-five-concepts]
backend/tests/test_concept_processing.py::test_more_than_five_concepts_rejected_by_shared_contract[TC-US04-15-six-concepts]
backend/tests/test_concept_processing.py::test_invalid_mocked_concepts_are_not_published[TC-US04-16-empty-concept-name]
backend/tests/test_concept_processing.py::test_invalid_mocked_concepts_are_not_published[TC-US04-17-missing-description]
backend/tests/test_concept_processing.py::test_invalid_mocked_concepts_are_not_published[TC-US04-18-empty-description]
backend/tests/test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions[TC-US04-19-known-page-keyword]
backend/tests/test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions[TC-US04-20-first-page-first-character]
backend/tests/test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions[TC-US04-21-last-page-last-character]
backend/tests/test_reader_extraction.py::test_reader_search_no_match_is_a_valid_empty_result[TC-US04-22-no-matches]
backend/tests/test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result[TC-US04-23-missing-query]
backend/tests/test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result[TC-US04-24-empty-query]
backend/tests/test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result[TC-US04-25-overlong-query]
backend/tests/test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result[TC-US04-26-whitespace-query]
backend/tests/test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result[TC-US04-27-punctuation-query]
backend/tests/test_reader_extraction.py::test_reader_page_text_preserves_physical_page_and_positions[TC-US04-28-first-page-text]
backend/tests/test_reader_extraction.py::test_reader_page_text_preserves_physical_page_and_positions[TC-US04-29-middle-page-text]
backend/tests/test_reader_extraction.py::test_reader_page_text_preserves_physical_page_and_positions[TC-US04-30-last-page-text]
backend/tests/test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages[TC-US04-31-page-zero]
backend/tests/test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages[TC-US04-32-negative-page]
backend/tests/test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages[TC-US04-33-one-past-last-page]
backend/tests/test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages[TC-US04-34-nonnumeric-page]
backend/tests/test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages[TC-US04-35-fractional-page]
backend/tests/test_reader_presentation.py::test_saved_citation_opens_matching_document_page_and_visible_highlight[TC-US09-01-citation-opens-exact-source]
backend/tests/test_reader_presentation.py::test_invalid_citation_is_removed_from_saved_reader_summary[TC-US09-02-reject-invalid-citation-page]
backend/tests/test_reader_presentation.py::test_invalid_citation_is_removed_from_saved_reader_summary[TC-US09-03-reject-invalid-citation-document]
backend/tests/test_reader_presentation.py::test_invalid_citation_is_removed_from_saved_reader_summary[TC-US09-04-reject-stale-citation]
backend/tests/test_reader_presentation.py::test_keyword_highlight_draws_only_at_known_match_positions[TC-US04-36-known-page-repeated-highlight]
backend/tests/test_reader_presentation.py::test_keyword_highlight_draws_only_at_known_match_positions[TC-US04-37-first-page-highlight]
backend/tests/test_reader_presentation.py::test_keyword_highlight_draws_only_at_known_match_positions[TC-US04-38-last-page-highlight]
backend/tests/test_reader_presentation.py::test_valid_query_without_highlights_returns_readable_pdf[TC-US04-39-highlight-no-match]
backend/tests/test_reader_presentation.py::test_valid_query_without_highlights_returns_readable_pdf[TC-US04-40-empty-highlight-query-clears-marks]
backend/tests/test_reader_presentation.py::test_exact_match_span_accepts_first_and_last_character_boundaries[TC-US04-55-valid-span-starts-at-zero]
backend/tests/test_reader_presentation.py::test_exact_match_span_accepts_first_and_last_character_boundaries[TC-US04-56-valid-span-ends-at-text-length]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-41-overlong-highlight-query]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-42-highlight-page-zero]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-43-highlight-negative-page]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-44-highlight-one-past-last-page]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-45-highlight-nonnumeric-page]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-46-highlight-fractional-page]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-47-highlight-missing-page]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-48-negative-match-start]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-49-match-end-past-text]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-50-match-start-at-text-end]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-51-empty-match-span]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-52-reversed-match-span]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-53-missing-match-end]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-54-missing-match-start]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-01-correct-document-page-bullet]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-01-correct-document-page-table]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-01-correct-document-page-concept]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-02-missing-evidence-unverified-bullet]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-02-missing-evidence-unverified-table]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-02-missing-evidence-unverified-concept]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-03-invalid-page-rejected-bullet]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-03-invalid-page-rejected-table]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-03-invalid-page-rejected-concept]
backend/tests/test_evidence_persistence.py::test_two_documents_supporting_one_bullet_claim_persist_distinct_citations[TC-US08-04-same-claim-two-documents]
backend/tests/test_evidence_persistence.py::test_two_documents_supporting_one_bullet_claim_persist_distinct_citations[TC-US08-05-same-claim-distinct-document-pages]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-06-persist-missing-source-unverified]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-07-reject-nonexistent-source-document]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-08-reject-source-page-with-different-text]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-09-reject-mismatched-source-quote]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-10-reject-stale-reader-source]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-11-preserve-valid-source-reject-invalid-source]
backend/tests/test_document_file.py::test_citation_page_selects_readable_original_without_changing_source[TC-US09-05-first-citation-page-file]
backend/tests/test_document_file.py::test_citation_page_selects_readable_original_without_changing_source[TC-US09-05-first-citation-page-rendered-file]
backend/tests/test_document_file.py::test_citation_page_selects_readable_original_without_changing_source[TC-US09-06-last-citation-page-file]
backend/tests/test_document_file.py::test_citation_page_selects_readable_original_without_changing_source[TC-US09-06-last-citation-page-rendered-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-07-page-zero-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-07-page-zero-rendered-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-08-negative-page-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-08-negative-page-rendered-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-09-page-past-last-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-09-page-past-last-rendered-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-10-nonnumeric-page-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-10-nonnumeric-page-rendered-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-11-fractional-page-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-11-fractional-page-rendered-file]
backend/tests/test_document_file.py::test_textless_page_remains_readable_but_cannot_accept_citation_span[TC-US09-12-image-only-page-readable]
backend/tests/test_document_file.py::test_textless_page_remains_readable_but_cannot_accept_citation_span[TC-US09-13-blank-page-readable]

============================== warnings summary ===============================
backend\.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\SE_AI66A\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
102/172 tests collected (70 deselected) in 0.88s

Exit code: 0
```

### Actual failing output with the deliberate defect

```text
$ D:\SE_AI66A\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_document_metadata_api.py -k TC-US04-02 -vv --tb=short -p no:cacheprovider --basetemp C:\Users\AD\AppData\Local\Temp\documind-story-main-4a4jzyeu\mutation-work
============================= test session starts =============================
platform win32 -- Python 3.12.6, pytest-9.1.1, pluggy-1.7.0 -- D:\SE_AI66A\backend\.venv\Scripts\python.exe
rootdir: D:\SE_AI66A
plugins: anyio-4.15.1
collecting ... collected 21 items / 17 deselected / 4 selected

backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-confirmed-TC-US04-02-at-80] FAILED [ 25%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-needs_review-TC-US04-02-at-80] FAILED [ 50%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-confirmed-TC-US04-02-at-80] FAILED [ 75%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-needs_review-TC-US04-02-at-80] FAILED [100%]

================================== FAILURES ===================================
_ test_confidence_threshold_values_persisted[unassigned-confirmed-TC-US04-02-at-80] _
backend\tests\test_document_metadata_api.py:162: in test_confidence_threshold_values_persisted
    assert result['label'] == {
E   AssertionError: assert {'ai_label': 'Fixed AI label', 'ai_confidence': 0.8, 'review_state': 'confirmed', 'confidence_level': 'low', 'user_label': 'Human label'} == {'ai_label': 'Fixed AI label', 'ai_confidence': 0.8, 'confidence_level': 'high', 'review_state': 'confirmed', 'user_label': 'Human label'}
E
E     Common items:
E     {'ai_confidence': 0.8,
E      'ai_label': 'Fixed AI label',
E      'review_state': 'confirmed',
E      'user_label': 'Human label'}
E     Differing items:
E     {'confidence_level': 'low'} != {'confidence_level': 'high'}
E
E     Full diff:
E       {
E           'ai_label': 'Fixed AI label',
E           'ai_confidence': 0.8,
E     -     'confidence_level': 'high',
E           'review_state': 'confirmed',
E     +     'confidence_level': 'low',
E           'user_label': 'Human label',
E       }
---------------------------- Captured stdout setup ----------------------------
Starting server (Database-first approach)...
-------------------------- Captured stdout teardown ---------------------------
Shutting down server...
_ test_confidence_threshold_values_persisted[unassigned-needs_review-TC-US04-02-at-80] _
backend\tests\test_document_metadata_api.py:162: in test_confidence_threshold_values_persisted
    assert result['label'] == {
E   AssertionError: assert {'ai_label': 'Fixed AI label', 'ai_confidence': 0.8, 'review_state': 'needs_review', 'confidence_level': 'low', 'user_label': None} == {'ai_label': 'Fixed AI label', 'ai_confidence': 0.8, 'confidence_level': 'high', 'review_state': 'needs_review', 'user_label': None}
E
E     Common items:
E     {'ai_confidence': 0.8,
E      'ai_label': 'Fixed AI label',
E      'review_state': 'needs_review',
E      'user_label': None}
E     Differing items:
E     {'confidence_level': 'low'} != {'confidence_level': 'high'}
E
E     Full diff:
E       {
E           'ai_label': 'Fixed AI label',
E           'ai_confidence': 0.8,
E     -     'confidence_level': 'high',
E           'review_state': 'needs_review',
E     +     'confidence_level': 'low',
E           'user_label': None,
E       }
---------------------------- Captured stdout setup ----------------------------
Starting server (Database-first approach)...
-------------------------- Captured stdout teardown ---------------------------
Shutting down server...
_ test_confidence_threshold_values_persisted[assigned-confirmed-TC-US04-02-at-80] _
backend\tests\test_document_metadata_api.py:162: in test_confidence_threshold_values_persisted
    assert result['label'] == {
E   AssertionError: assert {'ai_label': 'Fixed AI label', 'ai_confidence': 0.8, 'review_state': 'confirmed', 'confidence_level': 'low', 'user_label': 'Human label'} == {'ai_label': 'Fixed AI label', 'ai_confidence': 0.8, 'confidence_level': 'high', 'review_state': 'confirmed', 'user_label': 'Human label'}
E
E     Common items:
E     {'ai_confidence': 0.8,
E      'ai_label': 'Fixed AI label',
E      'review_state': 'confirmed',
E      'user_label': 'Human label'}
E     Differing items:
E     {'confidence_level': 'low'} != {'confidence_level': 'high'}
E
E     Full diff:
E       {
E           'ai_label': 'Fixed AI label',
E           'ai_confidence': 0.8,
E     -     'confidence_level': 'high',
E           'review_state': 'confirmed',
E     +     'confidence_level': 'low',
E           'user_label': 'Human label',
E       }
---------------------------- Captured stdout setup ----------------------------
Starting server (Database-first approach)...
-------------------------- Captured stdout teardown ---------------------------
Shutting down server...
_ test_confidence_threshold_values_persisted[assigned-needs_review-TC-US04-02-at-80] _
backend\tests\test_document_metadata_api.py:162: in test_confidence_threshold_values_persisted
    assert result['label'] == {
E   AssertionError: assert {'ai_label': 'Fixed AI label', 'ai_confidence': 0.8, 'review_state': 'needs_review', 'confidence_level': 'low', 'user_label': None} == {'ai_label': 'Fixed AI label', 'ai_confidence': 0.8, 'confidence_level': 'high', 'review_state': 'needs_review', 'user_label': None}
E
E     Common items:
E     {'ai_confidence': 0.8,
E      'ai_label': 'Fixed AI label',
E      'review_state': 'needs_review',
E      'user_label': None}
E     Differing items:
E     {'confidence_level': 'low'} != {'confidence_level': 'high'}
E
E     Full diff:
E       {
E           'ai_label': 'Fixed AI label',
E           'ai_confidence': 0.8,
E     -     'confidence_level': 'high',
E           'review_state': 'needs_review',
E     +     'confidence_level': 'low',
E           'user_label': None,
E       }
---------------------------- Captured stdout setup ----------------------------
Starting server (Database-first approach)...
-------------------------- Captured stdout teardown ---------------------------
Shutting down server...
============================== warnings summary ===============================
backend\.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\SE_AI66A\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

backend/tests/test_document_metadata_api.py: 22 warnings
  D:\SE_AI66A\backend\.venv\Lib\site-packages\sqlalchemy\sql\schema.py:3627: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore

backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-confirmed-TC-US04-02-at-80]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-needs_review-TC-US04-02-at-80]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-confirmed-TC-US04-02-at-80]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-needs_review-TC-US04-02-at-80]
  D:\SE_AI66A\backend\app\core\security.py:22: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-confirmed-TC-US04-02-at-80] - AssertionError: assert {'ai_label': 'Fixed AI label', 'ai_confidence': 0.8, 'review_state': 'confirmed', 'confidence_level': 'low', 'user_label': 'Human label'} == {'ai_label': 'Fixed AI label', 'ai_confidence': 0.8, 'confidence_level': 'high', 'review_state': 'confirmed', 'user_label': 'Human label'}

  Common items:
  {'ai_confidence': 0.8,
   'ai_label': 'Fixed AI label',
   'review_state': 'confirmed',
   'user_label': 'Human label'}
  Differing items:
  {'confidence_level': 'low'} != {'confidence_level': 'high'}

  Full diff:
    {
        'ai_label': 'Fixed AI label',
        'ai_confidence': 0.8,
  -     'confidence_level': 'high',
        'review_state': 'confirmed',
  +     'confidence_level': 'low',
        'user_label': 'Human label',
    }
FAILED backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-needs_review-TC-US04-02-at-80] - AssertionError: assert {'ai_label': 'Fixed AI label', 'ai_confidence': 0.8, 'review_state': 'needs_review', 'confidence_level': 'low', 'user_label': None} == {'ai_label': 'Fixed AI label', 'ai_confidence': 0.8, 'confidence_level': 'high', 'review_state': 'needs_review', 'user_label': None}

  Common items:
  {'ai_confidence': 0.8,
   'ai_label': 'Fixed AI label',
   'review_state': 'needs_review',
   'user_label': None}
  Differing items:
  {'confidence_level': 'low'} != {'confidence_level': 'high'}

  Full diff:
    {
        'ai_label': 'Fixed AI label',
        'ai_confidence': 0.8,
  -     'confidence_level': 'high',
        'review_state': 'needs_review',
  +     'confidence_level': 'low',
        'user_label': None,
    }
FAILED backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-confirmed-TC-US04-02-at-80] - AssertionError: assert {'ai_label': 'Fixed AI label', 'ai_confidence': 0.8, 'review_state': 'confirmed', 'confidence_level': 'low', 'user_label': 'Human label'} == {'ai_label': 'Fixed AI label', 'ai_confidence': 0.8, 'confidence_level': 'high', 'review_state': 'confirmed', 'user_label': 'Human label'}

  Common items:
  {'ai_confidence': 0.8,
   'ai_label': 'Fixed AI label',
   'review_state': 'confirmed',
   'user_label': 'Human label'}
  Differing items:
  {'confidence_level': 'low'} != {'confidence_level': 'high'}

  Full diff:
    {
        'ai_label': 'Fixed AI label',
        'ai_confidence': 0.8,
  -     'confidence_level': 'high',
        'review_state': 'confirmed',
  +     'confidence_level': 'low',
        'user_label': 'Human label',
    }
FAILED backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-needs_review-TC-US04-02-at-80] - AssertionError: assert {'ai_label': 'Fixed AI label', 'ai_confidence': 0.8, 'review_state': 'needs_review', 'confidence_level': 'low', 'user_label': None} == {'ai_label': 'Fixed AI label', 'ai_confidence': 0.8, 'confidence_level': 'high', 'review_state': 'needs_review', 'user_label': None}

  Common items:
  {'ai_confidence': 0.8,
   'ai_label': 'Fixed AI label',
   'review_state': 'needs_review',
   'user_label': None}
  Differing items:
  {'confidence_level': 'low'} != {'confidence_level': 'high'}

  Full diff:
    {
        'ai_label': 'Fixed AI label',
        'ai_confidence': 0.8,
  -     'confidence_level': 'high',
        'review_state': 'needs_review',
  +     'confidence_level': 'low',
        'user_label': None,
    }
================ 4 failed, 17 deselected, 27 warnings in 8.76s ================

Exit code: 1
```

### Actual first restored run: temporary-file permission failure

```text
$ D:\SE_AI66A\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_document_metadata_api.py backend/tests/test_concept_processing.py backend/tests/test_reader_extraction.py backend/tests/test_reader_presentation.py backend/tests/test_evidence.py backend/tests/test_evidence_persistence.py backend/tests/test_document_file.py -k "TC-US04 or TC-US08 or TC-US09" -vv --tb=short -p no:cacheprovider --basetemp C:\Users\AD\AppData\Local\Temp\documind-story-main-4a4jzyeu\passing-work
============================= test session starts =============================
platform win32 -- Python 3.12.6, pytest-9.1.1, pluggy-1.7.0 -- D:\SE_AI66A\backend\.venv\Scripts\python.exe
rootdir: D:\SE_AI66A
plugins: anyio-4.15.1
collecting ... collected 172 items / 70 deselected / 102 selected

backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-confirmed-TC-US04-01-below-80] PASSED [  0%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-confirmed-TC-US04-02-at-80] PASSED [  1%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-confirmed-TC-US04-03-above-80] PASSED [  2%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-needs_review-TC-US04-01-below-80] PASSED [  3%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-needs_review-TC-US04-02-at-80] PASSED [  4%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-needs_review-TC-US04-03-above-80] PASSED [  5%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-confirmed-TC-US04-01-below-80] PASSED [  6%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-confirmed-TC-US04-02-at-80] PASSED [  7%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-confirmed-TC-US04-03-above-80] PASSED [  8%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-needs_review-TC-US04-01-below-80] PASSED [  9%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-needs_review-TC-US04-02-at-80] PASSED [ 10%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-needs_review-TC-US04-03-above-80] PASSED [ 11%]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-04-empty-label] PASSED [ 12%]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-05-long-label] PASSED [ 13%]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-06-missing-confidence] PASSED [ 14%]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-07-missing-label] PASSED [ 15%]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-08-negative-confidence] FAILED [ 16%]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-09-confidence-over-100] PASSED [ 17%]
backend/tests/test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence[TC-US04-10-two-concepts-generated-limitation] PASSED [ 18%]
backend/tests/test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence[TC-US04-11-two-concepts-explicit-limitation] PASSED [ 19%]
backend/tests/test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence[TC-US04-12-three-concepts] PASSED [ 20%]
backend/tests/test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence[TC-US04-13-four-concepts] PASSED [ 21%]
backend/tests/test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence[TC-US04-14-five-concepts] PASSED [ 22%]
backend/tests/test_concept_processing.py::test_more_than_five_concepts_rejected_by_shared_contract[TC-US04-15-six-concepts] PASSED [ 23%]
backend/tests/test_concept_processing.py::test_invalid_mocked_concepts_are_not_published[TC-US04-16-empty-concept-name] PASSED [ 24%]
backend/tests/test_concept_processing.py::test_invalid_mocked_concepts_are_not_published[TC-US04-17-missing-description] PASSED [ 25%]
backend/tests/test_concept_processing.py::test_invalid_mocked_concepts_are_not_published[TC-US04-18-empty-description] PASSED [ 26%]
backend/tests/test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions[TC-US04-19-known-page-keyword] PASSED [ 27%]
backend/tests/test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions[TC-US04-20-first-page-first-character] PASSED [ 28%]
backend/tests/test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions[TC-US04-21-last-page-last-character] PASSED [ 29%]
backend/tests/test_reader_extraction.py::test_reader_search_no_match_is_a_valid_empty_result[TC-US04-22-no-matches] PASSED [ 30%]
backend/tests/test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result[TC-US04-23-missing-query] PASSED [ 31%]
backend/tests/test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result[TC-US04-24-empty-query] PASSED [ 32%]
backend/tests/test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result[TC-US04-25-overlong-query] PASSED [ 33%]
backend/tests/test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result[TC-US04-26-whitespace-query] PASSED [ 34%]
backend/tests/test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result[TC-US04-27-punctuation-query] PASSED [ 35%]
backend/tests/test_reader_extraction.py::test_reader_page_text_preserves_physical_page_and_positions[TC-US04-28-first-page-text] PASSED [ 36%]
backend/tests/test_reader_extraction.py::test_reader_page_text_preserves_physical_page_and_positions[TC-US04-29-middle-page-text] PASSED [ 37%]
backend/tests/test_reader_extraction.py::test_reader_page_text_preserves_physical_page_and_positions[TC-US04-30-last-page-text] PASSED [ 38%]
backend/tests/test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages[TC-US04-31-page-zero] PASSED [ 39%]
backend/tests/test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages[TC-US04-32-negative-page] PASSED [ 40%]
backend/tests/test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages[TC-US04-33-one-past-last-page] PASSED [ 41%]
backend/tests/test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages[TC-US04-34-nonnumeric-page] PASSED [ 42%]
backend/tests/test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages[TC-US04-35-fractional-page] PASSED [ 43%]
backend/tests/test_reader_presentation.py::test_saved_citation_opens_matching_document_page_and_visible_highlight[TC-US09-01-citation-opens-exact-source] PASSED [ 44%]
backend/tests/test_reader_presentation.py::test_invalid_citation_is_removed_from_saved_reader_summary[TC-US09-02-reject-invalid-citation-page] PASSED [ 45%]
backend/tests/test_reader_presentation.py::test_invalid_citation_is_removed_from_saved_reader_summary[TC-US09-03-reject-invalid-citation-document] PASSED [ 46%]
backend/tests/test_reader_presentation.py::test_invalid_citation_is_removed_from_saved_reader_summary[TC-US09-04-reject-stale-citation] PASSED [ 47%]
backend/tests/test_reader_presentation.py::test_keyword_highlight_draws_only_at_known_match_positions[TC-US04-36-known-page-repeated-highlight] PASSED [ 48%]
backend/tests/test_reader_presentation.py::test_keyword_highlight_draws_only_at_known_match_positions[TC-US04-37-first-page-highlight] PASSED [ 49%]
backend/tests/test_reader_presentation.py::test_keyword_highlight_draws_only_at_known_match_positions[TC-US04-38-last-page-highlight] PASSED [ 50%]
backend/tests/test_reader_presentation.py::test_valid_query_without_highlights_returns_readable_pdf[TC-US04-39-highlight-no-match] PASSED [ 50%]
backend/tests/test_reader_presentation.py::test_valid_query_without_highlights_returns_readable_pdf[TC-US04-40-empty-highlight-query-clears-marks] PASSED [ 51%]
backend/tests/test_reader_presentation.py::test_exact_match_span_accepts_first_and_last_character_boundaries[TC-US04-55-valid-span-starts-at-zero] PASSED [ 52%]
backend/tests/test_reader_presentation.py::test_exact_match_span_accepts_first_and_last_character_boundaries[TC-US04-56-valid-span-ends-at-text-length] PASSED [ 53%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-41-overlong-highlight-query] PASSED [ 54%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-42-highlight-page-zero] PASSED [ 55%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-43-highlight-negative-page] PASSED [ 56%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-44-highlight-one-past-last-page] PASSED [ 57%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-45-highlight-nonnumeric-page] PASSED [ 58%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-46-highlight-fractional-page] PASSED [ 59%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-47-highlight-missing-page] PASSED [ 60%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-48-negative-match-start] PASSED [ 61%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-49-match-end-past-text] PASSED [ 62%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-50-match-start-at-text-end] PASSED [ 63%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-51-empty-match-span] PASSED [ 64%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-52-reversed-match-span] PASSED [ 65%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-53-missing-match-end] PASSED [ 66%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-54-missing-match-start] PASSED [ 67%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-01-correct-document-page-bullet] PASSED [ 68%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-01-correct-document-page-table] PASSED [ 69%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-01-correct-document-page-concept] PASSED [ 70%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-02-missing-evidence-unverified-bullet] PASSED [ 71%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-02-missing-evidence-unverified-table] PASSED [ 72%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-02-missing-evidence-unverified-concept] PASSED [ 73%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-03-invalid-page-rejected-bullet] PASSED [ 74%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-03-invalid-page-rejected-table] PASSED [ 75%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-03-invalid-page-rejected-concept] PASSED [ 76%]
backend/tests/test_evidence_persistence.py::test_two_documents_supporting_one_bullet_claim_persist_distinct_citations[TC-US08-04-same-claim-two-documents] PASSED [ 77%]
backend/tests/test_evidence_persistence.py::test_two_documents_supporting_one_bullet_claim_persist_distinct_citations[TC-US08-05-same-claim-distinct-document-pages] PASSED [ 78%]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-06-persist-missing-source-unverified] PASSED [ 79%]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-07-reject-nonexistent-source-document] PASSED [ 80%]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-08-reject-source-page-with-different-text] PASSED [ 81%]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-09-reject-mismatched-source-quote] PASSED [ 82%]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-10-reject-stale-reader-source] PASSED [ 83%]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-11-preserve-valid-source-reject-invalid-source] PASSED [ 84%]
backend/tests/test_document_file.py::test_citation_page_selects_readable_original_without_changing_source[TC-US09-05-first-citation-page-file] PASSED [ 85%]
backend/tests/test_document_file.py::test_citation_page_selects_readable_original_without_changing_source[TC-US09-05-first-citation-page-rendered-file] PASSED [ 86%]
backend/tests/test_document_file.py::test_citation_page_selects_readable_original_without_changing_source[TC-US09-06-last-citation-page-file] PASSED [ 87%]
backend/tests/test_document_file.py::test_citation_page_selects_readable_original_without_changing_source[TC-US09-06-last-citation-page-rendered-file] PASSED [ 88%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-07-page-zero-file] PASSED [ 89%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-07-page-zero-rendered-file] PASSED [ 90%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-08-negative-page-file] PASSED [ 91%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-08-negative-page-rendered-file] PASSED [ 92%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-09-page-past-last-file] PASSED [ 93%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-09-page-past-last-rendered-file] PASSED [ 94%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-10-nonnumeric-page-file] PASSED [ 95%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-10-nonnumeric-page-rendered-file] PASSED [ 96%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-11-fractional-page-file] PASSED [ 97%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-11-fractional-page-rendered-file] PASSED [ 98%]
backend/tests/test_document_file.py::test_textless_page_remains_readable_but_cannot_accept_citation_span[TC-US09-12-image-only-page-readable] PASSED [ 99%]
backend/tests/test_document_file.py::test_textless_page_remains_readable_but_cannot_accept_citation_span[TC-US09-13-blank-page-readable] PASSED [100%]

================================== FAILURES ===================================
_ test_invalid_mocked_label_is_not_published[TC-US04-08-negative-confidence] __
backend\tests\test_document_metadata_api.py:220: in test_invalid_mocked_label_is_not_published
    assert 'invalid_result' in saved['job_files'][0]['error_message']
E   AssertionError: assert 'invalid_result' in 'Document processing failed. Please retry.'
---------------------------- Captured stdout setup ----------------------------
Starting server (Database-first approach)...
------------------------------ Captured log call ------------------------------
ERROR    app.services.processing:processing.py:197 job=1 document=1 attempt=1/3 failed
Traceback (most recent call last):
  File "D:\SE_AI66A\backend\app\services\processing.py", line 126, in _process_job
    prepared = await asyncio.wait_for(prepare_document(source, on_page_count=on_page_count),
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\AD\AppData\Local\Programs\Python\Python312\Lib\asyncio\tasks.py", line 520, in wait_for
    return await fut
           ^^^^^^^^^
  File "D:\SE_AI66A\backend\app\services\job_extraction.py", line 78, in prepare_document
    count = json.loads(progress.read_text(encoding='utf-8'))['page_count']
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\AD\AppData\Local\Programs\Python\Python312\Lib\pathlib.py", line 1027, in read_text
    with self.open(mode='r', encoding=encoding, errors=errors) as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\AD\AppData\Local\Programs\Python\Python312\Lib\pathlib.py", line 1013, in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
PermissionError: [Errno 13] Permission denied: 'C:\\Users\\AD\\AppData\\Local\\Temp\\documind-job-zhyl11b5\\page_count.json'
-------------------------- Captured stdout teardown ---------------------------
Shutting down server...
============================== warnings summary ===============================
backend\.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\SE_AI66A\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

backend/tests/test_document_metadata_api.py: 102 warnings
backend/tests/test_concept_processing.py: 61 warnings
backend/tests/test_reader_extraction.py: 68 warnings
backend/tests/test_reader_presentation.py: 120 warnings
backend/tests/test_evidence.py: 81 warnings
backend/tests/test_evidence_persistence.py: 76 warnings
backend/tests/test_document_file.py: 48 warnings
  D:\SE_AI66A\backend\.venv\Lib\site-packages\sqlalchemy\sql\schema.py:3627: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore

backend/tests/test_document_metadata_api.py: 18 warnings
backend/tests/test_concept_processing.py: 9 warnings
backend/tests/test_reader_extraction.py: 17 warnings
backend/tests/test_reader_presentation.py: 25 warnings
backend/tests/test_evidence.py: 9 warnings
backend/tests/test_evidence_persistence.py: 8 warnings
backend/tests/test_document_file.py: 16 warnings
  D:\SE_AI66A\backend\app\core\security.py:22: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

backend/tests/test_document_metadata_api.py: 12 warnings
backend/tests/test_reader_extraction.py: 6 warnings
backend/tests/test_reader_presentation.py: 10 warnings
backend/tests/test_evidence.py: 3 warnings
backend/tests/test_evidence_persistence.py: 4 warnings
backend/tests/test_document_file.py: 10 warnings
  D:\SE_AI66A\backend\app\services\document_retention.py:13: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    return datetime.utcnow()

backend/tests/test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions[TC-US04-19-known-page-keyword]
backend/tests/test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions[TC-US04-20-first-page-first-character]
backend/tests/test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions[TC-US04-21-last-page-last-character]
backend/tests/test_reader_extraction.py::test_reader_search_no_match_is_a_valid_empty_result[TC-US04-22-no-matches]
  D:\SE_AI66A\backend\app\services\search_index.py:182: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = now or datetime.utcnow()

backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-07-page-zero-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-08-negative-page-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-09-page-past-last-file]
  D:\SE_AI66A\backend\.venv\Lib\site-packages\anyio\_backends\_asyncio.py:1100: StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
    result = context.run(func, *args)

backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-07-page-zero-rendered-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-08-negative-page-rendered-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-09-page-past-last-rendered-file]
  D:\SE_AI66A\backend\app\api\document.py:297: StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
    return get_document_file(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-08-negative-confidence] - AssertionError: assert 'invalid_result' in 'Document processing failed. Please retry.'
========= 1 failed, 101 passed, 70 deselected, 714 warnings in 51.52s =========

Exit code: 1
```

### Actual passing output after restoration and retry

```text
$ D:\SE_AI66A\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_document_metadata_api.py backend/tests/test_concept_processing.py backend/tests/test_reader_extraction.py backend/tests/test_reader_presentation.py backend/tests/test_evidence.py backend/tests/test_evidence_persistence.py backend/tests/test_document_file.py -k "TC-US04 or TC-US08 or TC-US09" -vv --tb=short -p no:cacheprovider --basetemp C:\Users\AD\AppData\Local\Temp\documind-story-retry-pw2nms16\pytest-work
============================= test session starts =============================
platform win32 -- Python 3.12.6, pytest-9.1.1, pluggy-1.7.0 -- D:\SE_AI66A\backend\.venv\Scripts\python.exe
rootdir: D:\SE_AI66A
plugins: anyio-4.15.1
collecting ... collected 172 items / 70 deselected / 102 selected

backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-confirmed-TC-US04-01-below-80] PASSED [  0%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-confirmed-TC-US04-02-at-80] PASSED [  1%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-confirmed-TC-US04-03-above-80] PASSED [  2%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-needs_review-TC-US04-01-below-80] PASSED [  3%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-needs_review-TC-US04-02-at-80] PASSED [  4%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[unassigned-needs_review-TC-US04-03-above-80] PASSED [  5%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-confirmed-TC-US04-01-below-80] PASSED [  6%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-confirmed-TC-US04-02-at-80] PASSED [  7%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-confirmed-TC-US04-03-above-80] PASSED [  8%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-needs_review-TC-US04-01-below-80] PASSED [  9%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-needs_review-TC-US04-02-at-80] PASSED [ 10%]
backend/tests/test_document_metadata_api.py::test_confidence_threshold_values_persisted[assigned-needs_review-TC-US04-03-above-80] PASSED [ 11%]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-04-empty-label] PASSED [ 12%]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-05-long-label] PASSED [ 13%]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-06-missing-confidence] PASSED [ 14%]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-07-missing-label] PASSED [ 15%]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-08-negative-confidence] PASSED [ 16%]
backend/tests/test_document_metadata_api.py::test_invalid_mocked_label_is_not_published[TC-US04-09-confidence-over-100] PASSED [ 17%]
backend/tests/test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence[TC-US04-10-two-concepts-generated-limitation] PASSED [ 18%]
backend/tests/test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence[TC-US04-11-two-concepts-explicit-limitation] PASSED [ 19%]
backend/tests/test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence[TC-US04-12-three-concepts] PASSED [ 20%]
backend/tests/test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence[TC-US04-13-four-concepts] PASSED [ 21%]
backend/tests/test_concept_processing.py::test_three_to_five_concepts_persisted_with_grounded_evidence[TC-US04-14-five-concepts] PASSED [ 22%]
backend/tests/test_concept_processing.py::test_more_than_five_concepts_rejected_by_shared_contract[TC-US04-15-six-concepts] PASSED [ 23%]
backend/tests/test_concept_processing.py::test_invalid_mocked_concepts_are_not_published[TC-US04-16-empty-concept-name] PASSED [ 24%]
backend/tests/test_concept_processing.py::test_invalid_mocked_concepts_are_not_published[TC-US04-17-missing-description] PASSED [ 25%]
backend/tests/test_concept_processing.py::test_invalid_mocked_concepts_are_not_published[TC-US04-18-empty-description] PASSED [ 26%]
backend/tests/test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions[TC-US04-19-known-page-keyword] PASSED [ 27%]
backend/tests/test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions[TC-US04-20-first-page-first-character] PASSED [ 28%]
backend/tests/test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions[TC-US04-21-last-page-last-character] PASSED [ 29%]
backend/tests/test_reader_extraction.py::test_reader_search_no_match_is_a_valid_empty_result[TC-US04-22-no-matches] PASSED [ 30%]
backend/tests/test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result[TC-US04-23-missing-query] PASSED [ 31%]
backend/tests/test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result[TC-US04-24-empty-query] PASSED [ 32%]
backend/tests/test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result[TC-US04-25-overlong-query] PASSED [ 33%]
backend/tests/test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result[TC-US04-26-whitespace-query] PASSED [ 34%]
backend/tests/test_reader_extraction.py::test_reader_search_invalid_query_is_not_a_no_match_result[TC-US04-27-punctuation-query] PASSED [ 35%]
backend/tests/test_reader_extraction.py::test_reader_page_text_preserves_physical_page_and_positions[TC-US04-28-first-page-text] PASSED [ 36%]
backend/tests/test_reader_extraction.py::test_reader_page_text_preserves_physical_page_and_positions[TC-US04-29-middle-page-text] PASSED [ 37%]
backend/tests/test_reader_extraction.py::test_reader_page_text_preserves_physical_page_and_positions[TC-US04-30-last-page-text] PASSED [ 38%]
backend/tests/test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages[TC-US04-31-page-zero] PASSED [ 39%]
backend/tests/test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages[TC-US04-32-negative-page] PASSED [ 40%]
backend/tests/test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages[TC-US04-33-one-past-last-page] PASSED [ 41%]
backend/tests/test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages[TC-US04-34-nonnumeric-page] PASSED [ 42%]
backend/tests/test_reader_extraction.py::test_reader_page_text_rejects_invalid_or_missing_pages[TC-US04-35-fractional-page] PASSED [ 43%]
backend/tests/test_reader_presentation.py::test_saved_citation_opens_matching_document_page_and_visible_highlight[TC-US09-01-citation-opens-exact-source] PASSED [ 44%]
backend/tests/test_reader_presentation.py::test_invalid_citation_is_removed_from_saved_reader_summary[TC-US09-02-reject-invalid-citation-page] PASSED [ 45%]
backend/tests/test_reader_presentation.py::test_invalid_citation_is_removed_from_saved_reader_summary[TC-US09-03-reject-invalid-citation-document] PASSED [ 46%]
backend/tests/test_reader_presentation.py::test_invalid_citation_is_removed_from_saved_reader_summary[TC-US09-04-reject-stale-citation] PASSED [ 47%]
backend/tests/test_reader_presentation.py::test_keyword_highlight_draws_only_at_known_match_positions[TC-US04-36-known-page-repeated-highlight] PASSED [ 48%]
backend/tests/test_reader_presentation.py::test_keyword_highlight_draws_only_at_known_match_positions[TC-US04-37-first-page-highlight] PASSED [ 49%]
backend/tests/test_reader_presentation.py::test_keyword_highlight_draws_only_at_known_match_positions[TC-US04-38-last-page-highlight] PASSED [ 50%]
backend/tests/test_reader_presentation.py::test_valid_query_without_highlights_returns_readable_pdf[TC-US04-39-highlight-no-match] PASSED [ 50%]
backend/tests/test_reader_presentation.py::test_valid_query_without_highlights_returns_readable_pdf[TC-US04-40-empty-highlight-query-clears-marks] PASSED [ 51%]
backend/tests/test_reader_presentation.py::test_exact_match_span_accepts_first_and_last_character_boundaries[TC-US04-55-valid-span-starts-at-zero] PASSED [ 52%]
backend/tests/test_reader_presentation.py::test_exact_match_span_accepts_first_and_last_character_boundaries[TC-US04-56-valid-span-ends-at-text-length] PASSED [ 53%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-41-overlong-highlight-query] PASSED [ 54%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-42-highlight-page-zero] PASSED [ 55%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-43-highlight-negative-page] PASSED [ 56%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-44-highlight-one-past-last-page] PASSED [ 57%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-45-highlight-nonnumeric-page] PASSED [ 58%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-46-highlight-fractional-page] PASSED [ 59%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-47-highlight-missing-page] PASSED [ 60%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-48-negative-match-start] PASSED [ 61%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-49-match-end-past-text] PASSED [ 62%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-50-match-start-at-text-end] PASSED [ 63%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-51-empty-match-span] PASSED [ 64%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-52-reversed-match-span] PASSED [ 65%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-53-missing-match-end] PASSED [ 66%]
backend/tests/test_reader_presentation.py::test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf[TC-US04-54-missing-match-start] PASSED [ 67%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-01-correct-document-page-bullet] PASSED [ 68%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-01-correct-document-page-table] PASSED [ 69%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-01-correct-document-page-concept] PASSED [ 70%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-02-missing-evidence-unverified-bullet] PASSED [ 71%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-02-missing-evidence-unverified-table] PASSED [ 72%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-02-missing-evidence-unverified-concept] PASSED [ 73%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-03-invalid-page-rejected-bullet] PASSED [ 74%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-03-invalid-page-rejected-table] PASSED [ 75%]
backend/tests/test_evidence.py::test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode[TC-US08-03-invalid-page-rejected-concept] PASSED [ 76%]
backend/tests/test_evidence_persistence.py::test_two_documents_supporting_one_bullet_claim_persist_distinct_citations[TC-US08-04-same-claim-two-documents] PASSED [ 77%]
backend/tests/test_evidence_persistence.py::test_two_documents_supporting_one_bullet_claim_persist_distinct_citations[TC-US08-05-same-claim-distinct-document-pages] PASSED [ 78%]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-06-persist-missing-source-unverified] PASSED [ 79%]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-07-reject-nonexistent-source-document] PASSED [ 80%]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-08-reject-source-page-with-different-text] PASSED [ 81%]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-09-reject-mismatched-source-quote] PASSED [ 82%]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-10-reject-stale-reader-source] PASSED [ 83%]
backend/tests/test_evidence_persistence.py::test_unverified_claim_persists_without_invalid_source_links[TC-US08-11-preserve-valid-source-reject-invalid-source] PASSED [ 84%]
backend/tests/test_document_file.py::test_citation_page_selects_readable_original_without_changing_source[TC-US09-05-first-citation-page-file] PASSED [ 85%]
backend/tests/test_document_file.py::test_citation_page_selects_readable_original_without_changing_source[TC-US09-05-first-citation-page-rendered-file] PASSED [ 86%]
backend/tests/test_document_file.py::test_citation_page_selects_readable_original_without_changing_source[TC-US09-06-last-citation-page-file] PASSED [ 87%]
backend/tests/test_document_file.py::test_citation_page_selects_readable_original_without_changing_source[TC-US09-06-last-citation-page-rendered-file] PASSED [ 88%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-07-page-zero-file] PASSED [ 89%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-07-page-zero-rendered-file] PASSED [ 90%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-08-negative-page-file] PASSED [ 91%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-08-negative-page-rendered-file] PASSED [ 92%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-09-page-past-last-file] PASSED [ 93%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-09-page-past-last-rendered-file] PASSED [ 94%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-10-nonnumeric-page-file] PASSED [ 95%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-10-nonnumeric-page-rendered-file] PASSED [ 96%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-11-fractional-page-file] PASSED [ 97%]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-11-fractional-page-rendered-file] PASSED [ 98%]
backend/tests/test_document_file.py::test_textless_page_remains_readable_but_cannot_accept_citation_span[TC-US09-12-image-only-page-readable] PASSED [ 99%]
backend/tests/test_document_file.py::test_textless_page_remains_readable_but_cannot_accept_citation_span[TC-US09-13-blank-page-readable] PASSED [100%]

============================== warnings summary ===============================
backend\.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\SE_AI66A\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

backend/tests/test_document_metadata_api.py: 102 warnings
backend/tests/test_concept_processing.py: 61 warnings
backend/tests/test_reader_extraction.py: 68 warnings
backend/tests/test_reader_presentation.py: 120 warnings
backend/tests/test_evidence.py: 81 warnings
backend/tests/test_evidence_persistence.py: 76 warnings
backend/tests/test_document_file.py: 48 warnings
  D:\SE_AI66A\backend\.venv\Lib\site-packages\sqlalchemy\sql\schema.py:3627: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore

backend/tests/test_document_metadata_api.py: 18 warnings
backend/tests/test_concept_processing.py: 9 warnings
backend/tests/test_reader_extraction.py: 17 warnings
backend/tests/test_reader_presentation.py: 25 warnings
backend/tests/test_evidence.py: 9 warnings
backend/tests/test_evidence_persistence.py: 8 warnings
backend/tests/test_document_file.py: 16 warnings
  D:\SE_AI66A\backend\app\core\security.py:22: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

backend/tests/test_document_metadata_api.py: 12 warnings
backend/tests/test_reader_extraction.py: 6 warnings
backend/tests/test_reader_presentation.py: 10 warnings
backend/tests/test_evidence.py: 3 warnings
backend/tests/test_evidence_persistence.py: 4 warnings
backend/tests/test_document_file.py: 10 warnings
  D:\SE_AI66A\backend\app\services\document_retention.py:13: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    return datetime.utcnow()

backend/tests/test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions[TC-US04-19-known-page-keyword]
backend/tests/test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions[TC-US04-20-first-page-first-character]
backend/tests/test_reader_extraction.py::test_reader_keyword_search_returns_known_page_and_source_positions[TC-US04-21-last-page-last-character]
backend/tests/test_reader_extraction.py::test_reader_search_no_match_is_a_valid_empty_result[TC-US04-22-no-matches]
  D:\SE_AI66A\backend\app\services\search_index.py:182: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    now = now or datetime.utcnow()

backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-07-page-zero-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-08-negative-page-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-09-page-past-last-file]
  D:\SE_AI66A\backend\.venv\Lib\site-packages\anyio\_backends\_asyncio.py:1100: StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
    result = context.run(func, *args)

backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-07-page-zero-rendered-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-08-negative-page-rendered-file]
backend/tests/test_document_file.py::test_invalid_citation_page_is_rejected_without_serving_file[TC-US09-09-page-past-last-rendered-file]
  D:\SE_AI66A\backend\app\api\document.py:297: StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
    return get_document_file(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
============== 102 passed, 70 deselected, 714 warnings in 53.66s ==============

Exit code: 0
```

## Commits and PR links

The test implementation commit/PR mapping was verified against GitHub `refs/pull/*/head` using `git ls-remote origin 'refs/pull/*/head'`.

| Scope | Commit | PR |
|---|---|---|
| US04 label/concept validation | [c3ad0b7](https://github.com/SE-FDA-NEU/G6_AI66A_SE/commit/c3ad0b71504781e3683d43a48529324a8be20258) | [#224](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/224) |
| US04 search/navigation/highlights | [bf111d8](https://github.com/SE-FDA-NEU/G6_AI66A_SE/commit/bf111d89d114d830e4f87b5415550fb0246fdbe1) | [#225](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/225) |
| US08 evidence integrity | [53e992a](https://github.com/SE-FDA-NEU/G6_AI66A_SE/commit/53e992a1c2ff262a9476c5ead51c4c9599e4eff0) | [#226](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/226) |
| US09 citation reader navigation | [d340083](https://github.com/SE-FDA-NEU/G6_AI66A_SE/commit/d340083c99f22e045d18f64d9607bcd803bdd1f1) | [#227](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/227) |

The earlier documentation handover was [b98f5a9](https://github.com/SE-FDA-NEU/G6_AI66A_SE/commit/b98f5a9965da9bb6979ffc5ded3534a02351f9ee), merged through [PR #234](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/234). This fresh run tests [main at b18793e](https://github.com/SE-FDA-NEU/G6_AI66A_SE/commit/b18793e679b9557927b6a248e6c3e2b67dddd7ca). Implementation PR-to-commit mappings above were verified again on 31 October using GitHub pull-request head refs.

The new handover branch is `docs/us04-us08-us09-evidence-20261031`, based on `main`. Its final diff must list only this document:

```powershell
git diff --name-status origin/main...HEAD
git log --oneline origin/main..HEAD -- docs/testing.md
```

The fresh evidence commit and PR link are recorded in the handover entry below.

## Scope of the evidence

The 70 deselected tests are outside this selected matrix. These are backend/API/PDF tests, not browser click evidence. US09-01 verifies saved-job association and visible source highlighting; US09-12/13 verify readable textless pages and rejection of fabricated spans. A browser test of Back to Results and its textless-page explanatory message is not claimed. The full repository/browser suite and warning-free execution are also not claimed.
