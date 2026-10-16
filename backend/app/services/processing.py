"""Background worker entry point; analysis is implemented in a separate task."""
from datetime import datetime, timezone

from app.models import Job, JobStatus


def process_job(job_id, session_factory):
    # Do not claim successful analysis before the actual processor is integrated.
    with session_factory() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = JobStatus.FAILED
        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        for file in job.job_files:
            file.status = JobStatus.FAILED
            file.attempt_count += 1
            file.error_message = "Document processing worker is not integrated yet."
        db.commit()
