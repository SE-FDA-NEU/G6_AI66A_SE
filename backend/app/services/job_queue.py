"""In-process background tasks, kept alive independently of HTTP requests."""
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import Request
from app.models import Job, JobStatus
from app.services.processing import process_job

logger = logging.getLogger(__name__)


def mark_failed(job_id, session_factory, message):
    with session_factory() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = JobStatus.FAILED
        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        for file in job.job_files:
            if file.status not in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.TIMED_OUT):
                file.status = JobStatus.FAILED
                file.error_message = message
        db.commit()


class JobQueue:
    def __init__(self, session_factory, processor=process_job):
        self.session_factory = session_factory
        self.processor = processor
        self.tasks = set()
        self.closing = False

    def enqueue(self, job_id):
        if self.closing:
            raise RuntimeError("Job queue is shutting down")
        task = asyncio.create_task(self._run(job_id), name=f"process-job-{job_id}")
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _run(self, job_id):
        try:
            # Synchronous processing/DB work must not block the event loop.
            await asyncio.to_thread(self.processor, job_id, self.session_factory)
        except Exception:
            logger.exception("Processing job %s failed", job_id)
            try:
                await asyncio.to_thread(mark_failed, job_id, self.session_factory,
                                        "Background processing failed. Please retry.")
            except Exception:
                logger.exception("Could not record failure for job %s", job_id)

    async def close(self):
        self.closing = True
        if self.tasks:
            await asyncio.gather(*tuple(self.tasks))


def get_job_queue(request: Request):
    return request.app.state.job_queue
