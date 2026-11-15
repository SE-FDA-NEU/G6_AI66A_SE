# Large-document summary processing

Bullet and Concept sources that exceed the configured input payload budget use
bounded hierarchical synthesis. Every distinct text excerpt is mapped; escaped
JSON is included in chunk-size accounting. Map calls return compact findings
rather than repeating a full overview for every chunk. When those findings are
still too large for one final request, inner reduction stages condense them in
bounded groups before final synthesis. Source IDs survive every stage so the
existing citation/evidence checks still apply. The final summary remains a
concise synthesis, not a verbatim copy of every page.

The output contract remains at most 16 bullet items / five concepts and 1,000
words. For sources with more than 15 required heading topics, coverage priorities
are distributed from the beginning through the end rather than demanding more
separate detail items than that contract permits. Compact inner stages do not
have to provide an executive overview or independently cover the whole source.
Malformed/partial JSON, provider blocking and invalid source evidence are not
accepted as successful analysis. A truncated Gemini response receives one
bounded correction with a larger output-token ceiling (at most 16,384).

## BR01 / BR02 boundaries are unchanged

| Boundary | Enforced behavior |
|---|---|
| Per-file upload | At most 5 MiB (5 × 1,048,576 bytes), checked before processing |
| Batch count | At most five PDF/DOCX/PPTX files; five valid 5 MiB files total 25 MiB |
| Per-document attempt | min(300, 30 + 3 × physical page count) seconds, as before |
| PDF Bullet target | 180 seconds, including queue delay and retries |
| Contract Table batch target | 300 seconds for the batch, including queue delay and retries |
| Provider request timer | Existing GEMINI_REQUEST_TIMEOUT_SECONDS (default 45); the outer BR deadline can cancel it sooner |
| Compact intermediate output | At most 2048 output tokens before a bounded repair |

No upload-size or processing-deadline setting is increased by this fix. The aim
is to finish within the same BR budgets by avoiding verbose repeated summaries,
oversized reduce requests and duplicate provider calls on retry. A late result
is still rejected; timeouts are shown as failure rather than false completion.

Successful intermediate provider responses are memoized only inside the current
job/file object. A later timeout can reuse those chunks during the same job's
retry; a different document/upload/account gets an independent memo. Personal
keys still bypass shared disk caches. No credentials or private source text are
added to operational logs. Memory is released when the job ends. Restart recovery
still requires reupload rather than claiming durable queued processing.

Gemini RetryInfo retry delays are recognized in JSON as well as Retry-After
headers; the existing bounded transport loop respects the request deadline and
does not retry an exhausted daily quota. Billing/quota exhaustion, inaccessible
provider models and image-only documents still need an explicit error or source
limitation rather than an invented summary.

## Verification and deployment

From backend, with development dependencies installed:

```bash
python -m pytest tests/test_large_document_summary.py tests/test_gemini_analysis.py tests/test_summary_quality.py tests/test_processing_timeouts.py tests/test_bullet_processing.py tests/test_concept_processing.py tests/test_job_lifecycle.py tests/test_job_restart_recovery.py -q
```

The regression uses an 80-page synthetic source, exercises inner reduction
stages, asserts every page is mapped and every provider payload is bounded,
checks first/last-page evidence, retries without repeating paid map work, checks
output-limit correction and verifies that even large source inputs still fail
visibly when a BR deadline expires. Existing upload size, short-document
deadline/cancellation and Table batch target tests are retained.

Deploy the reviewed successful CI commit to the existing Render backend, retaining
its DB and persistent storage. No environment changes are required. Keep the existing BR upload/timeout
settings. The queue must finish or stop before a replacement starts. Previously failed jobs
remain failed history entries; upload the source again to use the new pipeline.
Record a fresh job URL and completion result after deployment; a branch push
alone does not prove production has changed.
