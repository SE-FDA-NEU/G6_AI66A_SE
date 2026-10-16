"""Per-document processing with bounded, cancellable attempts."""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.models import Job, JobStatus

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3


def document_timeout(page_count):
    """Unknown page counts use the baseline until extraction is integrated."""
    return min(300, 30 + 3 * max(0, page_count or 0))


@dataclass(frozen=True)
class DocumentInput:
    id: int
    storage_path: str
    page_count: int | None


class ProcessingNotConfigured(Exception):
    pass


async def process_document(document, mode):
    """Integration point for cancellable async processing, without DB access.

    Do not block this event loop. CPU work must use a terminable subprocess,
    not an uncancellable thread. Results are persisted only after success.
    """
    raise ProcessingNotConfigured("Document processing worker is not integrated yet.")


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _process_job(job_id, session_factory, processor):
    with session_factory() as db:
        job = db.get(Job, job_id)
        if job is None or job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            return
        job.status = JobStatus.PROCESSING
        job.finished_at = None
        db.commit()

        for file in job.job_files:
            if file.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                continue
            document = file.document
            source = DocumentInput(document.id, document.storage_path, document.page_count)
            timeout = document_timeout(document.page_count)
            file.timeout_seconds = timeout

            while file.attempt_count < MAX_ATTEMPTS:
                file.attempt_count += 1
                attempt = file.attempt_count
                file.status = JobStatus.PROCESSING
                file.error_message = None
                db.commit()
                logger.info("job=%s document=%s attempt=%s/%s timeout=%ss started",
                            job_id, source.id, attempt, MAX_ATTEMPTS, timeout)
                try:
                    # Cancel and await cleanup before starting the next attempt.
                    result = await asyncio.wait_for(processor(source, job.mode), timeout=timeout)
                except TimeoutError:
                    file.status = JobStatus.TIMED_OUT
                    file.error_message = f"Processing exceeded {timeout} seconds (attempt {attempt}/{MAX_ATTEMPTS})."
                    db.commit()
                    logger.warning("job=%s document=%s attempt=%s/%s timed_out timeout=%ss",
                                   job_id, source.id, attempt, MAX_ATTEMPTS, timeout)
                    continue
                except ProcessingNotConfigured as error:
                    file.status = JobStatus.FAILED
                    file.error_message = str(error)
                    db.commit()
                    logger.error("job=%s document=%s attempt=%s/%s failed: processor not integrated",
                                 job_id, source.id, attempt, MAX_ATTEMPTS)
                    break
                except Exception:
                    file.status = JobStatus.FAILED
                    file.error_message = "Document processing failed. Please retry."
                    db.commit()
                    logger.exception("job=%s document=%s attempt=%s/%s failed",
                                     job_id, source.id, attempt, MAX_ATTEMPTS)
                    break
                else:
                    file.status = JobStatus.COMPLETED
                    file.error_message = None
                    if result is not None:
                        results = dict(job.result_data or {})
                        documents = dict(results.get('documents', {}))
                        documents[str(source.id)] = result
                        results['documents'] = documents
                        job.result_data = results
                    job.completed_count = sum(item.status == JobStatus.COMPLETED for item in job.job_files)
                    db.commit()
                    logger.info("job=%s document=%s attempt=%s/%s completed",
                                job_id, source.id, attempt, MAX_ATTEMPTS)
                    break

            if file.status not in (JobStatus.COMPLETED, JobStatus.FAILED):
                file.status = JobStatus.FAILED
                file.error_message = f"Processing timed out after {MAX_ATTEMPTS} attempts ({timeout} seconds per attempt)."
                db.commit()
                logger.error("job=%s document=%s failed after %s attempts",
                             job_id, source.id, file.attempt_count)

        job.completed_count = sum(item.status == JobStatus.COMPLETED for item in job.job_files)
        job.status = (JobStatus.COMPLETED if job.job_files and
                      job.completed_count == len(job.job_files) else JobStatus.FAILED)
        job.finished_at = utcnow()
        db.commit()


def process_job(job_id, session_factory, processor=None):
    """Queue entry point; JobQueue calls this outside the HTTP event loop."""
    asyncio.run(_process_job(job_id, session_factory, processor or process_document))
