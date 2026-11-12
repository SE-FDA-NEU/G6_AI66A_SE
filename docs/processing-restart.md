# Processing across restart and deployment

The queue is in memory: run exactly one backend instance and one Uvicorn worker.
Do not overlap old/new deployments, use rolling multi-instance replacement, or
share this database with a second worker. Startup recovery assumes the old
process (including its extraction children) is fully stopped. It is not a durable
queue, distributed lease or automatic resume implementation.

## Startup and user-visible behavior

Before the queue and retention scheduler start, the API fails abandoned pending,
processing or timed-out jobs in bounded batches. Completed files/results,
citations and originals remain intact. Unfinished files become failed with:
`Processing was interrupted by a server restart or deployment. Please upload the unfinished files again.`
The completed count and finished time are persisted. Terminal jobs are unchanged;
running recovery twice has no additional effect. Recovery must succeed before
startup completes; a DB failure prevents accepting uploads with unreconciled state.

The in-process queue ignores duplicate enqueues while a job is active. A default
worker re-reads terminal state before publishing output, so a late result cannot
turn a recovered failure into success. This does not provide cross-process
exactly-once delivery or allow manual recovery while a live worker is running.

## Shutdown budget

The queue stops accepting work, then waits up to `JOB_SHUTDOWN_GRACE_SECONDS`
(default 10). It requests cancellation on the actual async processing coroutine
inside each worker thread and waits up to `JOB_SHUTDOWN_CLEANUP_SECONDS` (default
8) for cleanup and failure persistence. Cancelling an outer `to_thread` await
alone would not stop the worker. Extraction cancellation terminates/reaps its
child before removing temporary work files; prepared artifacts close in finally.

Host shutdown time must exceed these budgets plus DB transaction and scheduler
cleanup time. Blocking drivers/custom synchronous processors are not forcibly
killable Python threads. If cleanup exceeds its budget, a sanitized error is
logged; the host must terminate the entire old process tree before replacement.
Hard kills skip graceful cleanup, so the next startup repairs stale DB state.
The host must remove terminated-container temp files and child processes; do not
delete original uploads as part of restart recovery.

## Deployment rehearsal

1. Record release SHA; confirm one instance/process and a stop-before-start deployment.
2. Upload a batch, capture job ID, partial progress and one saved result.
3. Restart during processing; also exercise forced termination in a disposable environment.
4. Start the replacement against the same DB and persistent STORAGE_DIR.
5. Verify a failed job with resubmission guidance, retained completed result/originals,
   no leftover extraction process, no duplicate publication, and a working new upload.
6. Reopen an older completed job and its reader/citation; confirm they are unchanged.

Automated regression command from backend:
`python -m pytest tests/test_job_restart_recovery.py tests/test_job_lifecycle.py tests/test_processing_timeouts.py tests/test_upload_jobs.py tests/test_extraction_pipeline.py -v`.
The tests use temporary storage/SQLite and controlled processors. Real hosting
shutdown limits and stop-before-start behavior must still be verified in #248/#252.
