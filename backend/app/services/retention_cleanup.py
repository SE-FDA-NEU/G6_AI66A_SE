"""Idempotent, bounded retention sweeps. No new tables or external scheduler."""
import asyncio
import logging
from pathlib import Path
import stat

from app.core.config import settings
from app.models import Citation, Document, Job, JobFile, JobStatus, ReviewState
from app.services.document_retention import utcnow, is_expired_source, EXPIRED_PATH_PREFIX

logger = logging.getLogger(__name__)
EXPIRED_MESSAGE = 'source_expired: Source expired and is no longer available.'


def _checked_path(path, root):
    """Reject traversal, symlinks and Windows junction/reparse points."""
    path = Path(path).absolute()
    root = Path(root).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('Cleanup path is outside document storage.')
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), 'st_file_attributes', 0) &
                                getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)):
            raise ValueError('Cleanup path contains a link or reparse point.')
    resolved = path.resolve()
    if not resolved.is_relative_to(root) or resolved == root:
        raise ValueError('Cleanup path resolves outside document storage.')
    return resolved


def _remove_files(db, document, storage_root):
    storage_root = Path(storage_root).resolve()
    owner_root = _checked_path(storage_root / str(document.owner_id), storage_root)
    original_path = document.storage_path.removeprefix(EXPIRED_PATH_PREFIX)
    source = _checked_path(original_path, owner_root)
    if db.query(Document.id).filter(Document.id != document.id,
                                    Document.storage_path.in_([original_path, EXPIRED_PATH_PREFIX + original_path])).first():
        raise ValueError('Another document references the same original file.')
    rendered = _checked_path(source.parent / '.reader' / str(document.id), owner_root)
    # Validate the whole tree before unlinking any entry; never recurse through links.
    entries = []
    if rendered.exists():
        pending = [rendered]
        while pending:
            directory = pending.pop()
            for entry in directory.iterdir():
                checked = _checked_path(entry, rendered)
                entries.append(checked)
                if checked.is_dir():
                    pending.append(checked)
    if source.exists() and not source.is_file():
        raise ValueError('Original path is not a regular file.')
    source.unlink(missing_ok=True)
    for entry in sorted(entries, key=lambda path: len(path.parts), reverse=True):
        if entry.is_dir():
            entry.rmdir()
        else:
            entry.unlink(missing_ok=True)
    if rendered.exists():
        rendered.rmdir()


def _expire_data(db, document):
    # Keep only a tombstone so existing owner-scoped URLs can return HTTP 410.
    if not is_expired_source(document):
        document.storage_path = EXPIRED_PATH_PREFIX + document.storage_path
    document.file_size_bytes = 0
    document.extracted_text = None  # also removes passage/semantic caches
    document.page_count = None
    document.ai_label = document.ai_confidence = document.user_label = None
    document.folder_id = None
    document.review_state = ReviewState.NEEDS_REVIEW
    job_ids = {row[0] for row in db.query(JobFile.job_id).filter_by(document_id=document.id)}
    job_ids.update(row[0] for row in db.query(Citation.job_id).filter_by(document_id=document.id))
    for job in db.query(Job).filter(Job.id.in_(job_ids)).order_by(Job.id).with_for_update():
        # A saved batch may contain cross-document claims; invalidate the entire
        # affected snapshot rather than retain a claim derived from a deleted source.
        job.result_data = None
        for file in job.job_files:
            if file.document_id == document.id:
                file.status = JobStatus.FAILED
                file.error_message = EXPIRED_MESSAGE
        job.completed_count = sum(file.status == JobStatus.COMPLETED for file in job.job_files)
        job.status = JobStatus.FAILED
        job.finished_at = job.finished_at or utcnow()
        db.query(Citation).filter_by(job_id=job.id).delete(synchronize_session=False)
    db.query(Citation).filter_by(document_id=document.id).delete(synchronize_session=False)


def cleanup_document(factory, document_id, cutoff, storage_root):
    with factory() as db:
        document = db.query(Document).filter_by(id=document_id).with_for_update().first()
        # The candidate list is only a hint. Renewal that committed before this
        # lock wins; never unlink files using a stale expiry snapshot.
        if document is None or document.expires_at > cutoff or not document.storage_path:
            return 'skipped'
        _expire_data(db, document)
        db.commit()  # durably remove content BEFORE deleting bytes; safe after crashes
    with factory() as db:
        document = db.query(Document).filter_by(id=document_id).with_for_update().first()
        if document is None or not is_expired_source(document) or not document.storage_path:
            return 'skipped'
        try:
            _remove_files(db, document, storage_root)
        except (OSError, ValueError):
            # Retain the original path only for a later retry. APIs remain 410,
            # and no extracted content or old result is readable in the meantime.
            logger.exception('Retention file cleanup failed document=%s; retry next sweep', document_id)
            return 'retry'
        document.storage_path = ''
        db.commit()
        return 'deleted'


def cleanup_expired_documents(factory, *, now=None, storage_root=None, batch_size=None):
    cutoff = now if now is not None else utcnow()
    storage_root = storage_root if storage_root is not None else settings.STORAGE_DIR
    batch_size = batch_size or settings.RETENTION_CLEANUP_BATCH_SIZE
    counts = {'deleted': 0, 'skipped': 0, 'retry': 0}
    last_id = 0
    while True:
        with factory() as db:
            ids = [row[0] for row in db.query(Document.id).filter(
                Document.id > last_id, Document.expires_at <= cutoff,
                Document.storage_path != '').order_by(Document.id).limit(batch_size)]
        if not ids:
            break
        for document_id in ids:
            try:
                outcome = cleanup_document(factory, document_id, cutoff, storage_root)
                counts[outcome] += 1
            except Exception:
                counts['retry'] += 1
                logger.exception('Retention cleanup transaction failed document=%s', document_id)
        last_id = ids[-1]
    # The optional Gemini wire cache is shared by identical uploads for one
    # owner and has no document manifest. Invalidate that owner's acceleration
    # cache, including late writes from an in-flight expired analysis.
    with factory() as db:
        owners = [row[0] for row in db.query(Document.owner_id).filter(
            (Document.storage_path == '') | Document.storage_path.startswith(EXPIRED_PATH_PREFIX)).distinct()]
    for owner_id in owners:
        try:
            cache_root = _checked_path(Path(storage_root).resolve() / '.analysis-cache', storage_root)
            owner_cache = _checked_path(cache_root / str(owner_id), cache_root)
            if owner_cache.exists():
                for entry in owner_cache.iterdir():
                    entry = _checked_path(entry, owner_cache)
                    if entry.is_file():
                        entry.unlink(missing_ok=True)
        except (OSError, ValueError):
            logger.exception('Retention analysis cache cleanup failed owner=%s; retry next sweep', owner_id)
    return counts


class RetentionCleanupScheduler:
    def __init__(self, factory, interval=None):
        self.factory = factory
        self.interval = interval if interval is not None else settings.RETENTION_CLEANUP_INTERVAL_SECONDS
        self.stopping = asyncio.Event()
        self.task = None

    def start(self):
        self.task = asyncio.create_task(self.run(), name='document-retention-cleanup')
        logger.info('Retention cleanup started interval=%ss', self.interval)

    async def run(self):
        while not self.stopping.is_set():
            try:
                counts = await asyncio.to_thread(cleanup_expired_documents, self.factory)
                logger.info('Retention cleanup completed %s', counts)
            except Exception:
                logger.exception('Retention sweep failed; scheduler will retry')
            try:
                await asyncio.wait_for(self.stopping.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                pass

    async def close(self):
        self.stopping.set()
        if self.task is not None:
            await self.task  # finish the current DB/file transaction before shutdown
