"""Per-document processing with bounded, cancellable attempts."""
import asyncio
import logging
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timezone

from app.models import FileFormat, Job, JobMode, JobStatus
from app.schemas.result import AnalysisResult, BulletOutput, ConceptOutput, JobResultData, TableOutput
from app.services.job_extraction import prepare_document
from app.services.reader_extraction import ReaderConversionError
from app.services.result_persistence import InvalidAnalysisResult, publish_reader, save_analysis, sync_citations
from app.core.config import settings
from app.services.gemini_analysis import GeminiAnalysisError, analyze_document
from app.services.document_retention import is_expired_source
from pydantic import ValidationError

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3
BULLET_TARGET_SECONDS = 180


def document_timeout(page_count):
    """The existing per-document processing budget, capped at five minutes."""
    return min(300, 30 + 3 * max(0, page_count or 0))


@dataclass(frozen=True)
class DocumentInput:
    id: int
    storage_path: str
    page_count: int | None
    file_format: object = None
    extracted_text: list | None = None
    owner_id: int | None = None
    language: str = "vi"


async def process_document(document, mode):
    """Use the selected provider, or persist an explicit extraction-only result."""
    key = settings.GROQ_API_KEY if settings.ANALYSIS_PROVIDER == 'groq' else settings.GEMINI_API_KEY
    if key.get_secret_value().strip():
        return await analyze_document(document, mode)
    outputs = {'bullet': BulletOutput, 'table': TableOutput, 'concept': ConceptOutput}
    warnings = ['analysis_not_configured']
    if not any(page['text'].strip() for page in document.extracted_text):
        warnings.append('no_text_layer')
    return AnalysisResult(analysis_status='not_configured', output=outputs[mode.value](), warnings=warnings)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _process_job(job_id, session_factory, processor, analyzer):
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
            if document.owner_id != job.owner_id:
                file.status = JobStatus.FAILED
                file.error_message = 'Document is not available to this job.'
                db.commit()
                continue
            source = DocumentInput(document.id, document.storage_path, document.page_count,
                                   document.file_format, document.extracted_text, document.owner_id,
                                   (job.result_data or {}).get("language") or "vi")
            timeout = document_timeout(document.page_count)
            file.timeout_seconds = timeout
            loop = asyncio.get_running_loop()
            deadline = None
            if job.mode == JobMode.BULLET and source.file_format == FileFormat.PDF:
                queued_for = max(0, (utcnow() - job.created_at).total_seconds())
                deadline = loop.time() + BULLET_TARGET_SECONDS - queued_for

            def remaining_budget(seconds):
                return min(seconds, deadline - loop.time()) if deadline is not None else seconds

            def check_target():
                if deadline is not None and loop.time() >= deadline:
                    raise TimeoutError

            while file.attempt_count < MAX_ATTEMPTS:
                file.attempt_count += 1
                attempt = file.attempt_count
                file.status = JobStatus.PROCESSING
                file.error_message = None
                db.commit()
                logger.info("job=%s document=%s attempt=%s/%s timeout=%ss started",
                            job_id, source.id, attempt, MAX_ATTEMPTS, timeout)
                prepared = None
                try:
                    started = asyncio.get_running_loop().time()
                    check_target()
                    remaining = remaining_budget(timeout)
                    if processor is None:
                        # Until physical pages are known, extraction may use the
                        # existing maximum budget. Its elapsed time still counts
                        # towards the actual 30 + 3 * pages deadline below.
                        def on_page_count(count):
                            nonlocal timeout, source
                            source = replace(source, page_count=count)
                            timeout = document_timeout(count)
                            file.timeout_seconds = timeout
                            db.commit()
                            return remaining_budget(timeout)
                        prepared = await asyncio.wait_for(prepare_document(source, on_page_count=on_page_count),
                                                          timeout=remaining_budget(timeout if source.page_count else 300))
                        source = replace(source, page_count=prepared.data['page_count'],
                                         extracted_text=deepcopy(prepared.data['extracted_text']))
                        timeout = document_timeout(source.page_count)
                        file.timeout_seconds = timeout
                        db.commit()
                        logger.info("job=%s document=%s attempt=%s/%s pages=%s timeout=%ss extracted",
                                    job_id, source.id, attempt, MAX_ATTEMPTS, source.page_count, timeout)
                        remaining = remaining_budget(timeout - (asyncio.get_running_loop().time() - started))
                        if remaining <= 0:
                            raise TimeoutError
                    # Cancel and await cleanup before starting the next attempt.
                    result = await asyncio.wait_for((processor or analyzer)(source, job.mode), timeout=remaining)
                    check_target()
                    # Cleanup may have claimed a source while the model ran.
                    # Lock and re-read before publishing any artifacts or JSON.
                    db.refresh(document, with_for_update=True)
                    if is_expired_source(document):
                        raise ReaderConversionError('source_expired', 'Source expired and is no longer available.')
                    db.refresh(job, with_for_update=True)
                    if prepared is not None:
                        with publish_reader(document, prepared):
                            result = save_analysis(db, job, document, prepared, result)
                            check_target()
                            _save_success(db, job, file, source.id, result, versioned=True)
                    else:
                        _save_success(db, job, file, source.id, result)
                except TimeoutError:
                    db.rollback()
                    if deadline is not None and loop.time() >= deadline:
                        file.status = JobStatus.FAILED
                        file.error_message = f'Bullet processing exceeded the {BULLET_TARGET_SECONDS}-second target.'
                        db.commit()
                        break
                    file.status = JobStatus.TIMED_OUT
                    file.error_message = f"Processing exceeded {timeout} seconds (attempt {attempt}/{MAX_ATTEMPTS})."
                    db.commit()
                    logger.warning("job=%s document=%s attempt=%s/%s timed_out timeout=%ss",
                                   job_id, source.id, attempt, MAX_ATTEMPTS, timeout)
                    continue
                except (ReaderConversionError, GeminiAnalysisError) as error:
                    db.rollback()
                    file.status = JobStatus.FAILED
                    file.error_message = f"{error.code}: {error}"
                    db.commit()
                    logger.warning("job=%s document=%s attempt=%s/%s failed code=%s",
                                   job_id, source.id, attempt, MAX_ATTEMPTS, error.code)
                    break
                except (InvalidAnalysisResult, ValidationError) as error:
                    db.rollback()
                    file.status = JobStatus.FAILED
                    validation = error if isinstance(error, ValidationError) else error.__cause__
                    details = []
                    if isinstance(validation, ValidationError):
                        for item in validation.errors()[:5]:
                            # Only structural paths/codes are needed, never
                            # validation input values, source text or secrets.
                            path = '.'.join(str(part)[:40] for part in item['loc'])[:120]
                            details.append(f"{path} ({item['type']})")
                    suffix = ' Fields: ' + '; '.join(details) if details else ''
                    file.error_message = 'invalid_result: Analysis output or evidence could not be validated.' + suffix
                    db.commit()
                    logger.error("job=%s document=%s invalid_result error_type=%s fields=%s",
                                 job_id, source.id, type(error).__name__, details)
                    break
                except Exception:
                    db.rollback()
                    file.status = JobStatus.FAILED
                    file.error_message = "Document processing failed. Please retry."
                    db.commit()
                    logger.exception("job=%s document=%s attempt=%s/%s failed",
                                     job_id, source.id, attempt, MAX_ATTEMPTS)
                    break
                else:
                    logger.info("job=%s document=%s attempt=%s/%s completed",
                                job_id, source.id, attempt, MAX_ATTEMPTS)
                    break
                finally:
                    if prepared is not None:
                        prepared.close()

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


def _save_success(db, job, file, document_id, result, versioned=False):
    file.status = JobStatus.COMPLETED
    file.error_message = None
    if result is not None:
        results = dict(job.result_data or {})
        documents = dict(results.get('documents', {}))
        documents[str(document_id)] = result
        results['documents'] = documents
        if versioned:
            results['schema_version'] = 1
            results = JobResultData.model_validate(results).model_dump(mode='json')
        job.result_data = results
        if versioned:
            sync_citations(db, job)
    job.completed_count = sum(item.status == JobStatus.COMPLETED for item in job.job_files)
    db.commit()


def process_job(job_id, session_factory, processor=None, *, analyzer=None):
    """Queue entry point, outside the HTTP event loop.

    analyzer is an async adapter returning AnalysisResult after native extraction.
    It must remain cancellable and avoid blocking the async event loop.
    processor is the existing low-level test/worker override; it owns extraction
    and its result shape. Normal queue execution always uses the full pipeline.
    """
    asyncio.run(_process_job(job_id, session_factory, processor, analyzer or process_document))
