"""In-process background tasks, kept alive independently of HTTP requests."""
import asyncio
import logging

from fastapi import Request
from app.core.config import settings
from app.services.processing import process_job, WorkerControl
from app.services.job_recovery import mark_failed, INTERRUPTED_MESSAGE
from app.services.analysis_credentials import use_gemini_key

logger = logging.getLogger(__name__)


class JobQueue:
    def __init__(self, session_factory, processor=process_job, *, grace_seconds=None, cleanup_seconds=None):
        self.session_factory = session_factory
        self.processor = processor
        self.tasks = set()
        self.closing = False
        self.jobs = {}
        self.controls = {}
        self.grace_seconds = settings.JOB_SHUTDOWN_GRACE_SECONDS if grace_seconds is None else grace_seconds
        self.cleanup_seconds = settings.JOB_SHUTDOWN_CLEANUP_SECONDS if cleanup_seconds is None else cleanup_seconds

    def enqueue(self, job_id, *, gemini_api_key=None):
        if self.closing:
            raise RuntimeError("Job queue is shutting down")
        if job_id in self.jobs:
            return self.jobs[job_id]
        self.controls[job_id] = WorkerControl()
        task = asyncio.create_task(self._run(job_id, gemini_api_key), name=f"process-job-{job_id}")
        self.tasks.add(task)
        self.jobs[job_id] = task
        def discard(done):
            self.tasks.discard(done)
            self.jobs.pop(job_id, None)
            self.controls.pop(job_id, None)
        task.add_done_callback(discard)
        return task

    async def _run(self, job_id, gemini_api_key=None):
        try:
            # Synchronous processing/DB work must not block the event loop.
            kwargs = {'control': self.controls[job_id]} if self.processor is process_job else {}
            with use_gemini_key(gemini_api_key):
                await asyncio.to_thread(self.processor, job_id, self.session_factory, **kwargs)
        except asyncio.CancelledError:
            try:
                await asyncio.to_thread(mark_failed, job_id, self.session_factory, INTERRUPTED_MESSAGE)
            except Exception:
                logger.error('Could not record interrupted job %s; recover on next startup', job_id)
        except Exception:
            logger.error("Processing job %s failed", job_id)
            try:
                await asyncio.to_thread(mark_failed, job_id, self.session_factory,
                                        "Background processing failed. Please retry.")
            except Exception:
                logger.error("Could not record failure for job %s", job_id)

    async def close(self):
        self.closing = True
        if self.tasks:
            _, pending = await asyncio.wait(tuple(self.tasks), timeout=self.grace_seconds)
            for job_id, task in tuple(self.jobs.items()):
                if task in pending:
                    self.controls[job_id].cancel()
            if pending:
                _, remaining = await asyncio.wait(pending, timeout=self.cleanup_seconds)
                if remaining:
                    # Blocking driver/custom code cannot be killed by cancelling a
                    # thread. The host must terminate this process before starting
                    # its replacement; startup recovery repairs remaining DB state.
                    logger.error('Worker shutdown exceeded cleanup budget; process termination required remaining=%s', len(remaining))


def get_job_queue(request: Request):
    return request.app.state.job_queue
