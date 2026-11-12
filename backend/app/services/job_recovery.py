"""Fail abandoned in-memory work without deleting persisted successes or files."""
from datetime import datetime, timezone

from app.models import Job, JobStatus

INTERRUPTED_MESSAGE = 'Processing was interrupted by a server restart or deployment. Please upload the unfinished files again.'


def fail_unfinished(job, message):
    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
        return False
    for file in job.job_files:
        if file.status not in (JobStatus.COMPLETED, JobStatus.FAILED):
            file.status = JobStatus.FAILED
            file.error_message = message
    job.completed_count = sum(file.status == JobStatus.COMPLETED for file in job.job_files)
    job.status = JobStatus.FAILED
    job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    return True


def mark_failed(job_id, session_factory, message):
    with session_factory() as db:
        job = db.query(Job).filter(Job.id == job_id).with_for_update().first()
        if job is not None and fail_unfinished(job, message):
            db.commit()


def recover_interrupted_jobs(session_factory):
    # Only valid with one instance/process and no old worker still running.
    count, last_id = 0, 0
    while True:
        with session_factory() as db:
            jobs = db.query(Job).filter(Job.id > last_id,
                Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING, JobStatus.TIMED_OUT])
            ).order_by(Job.id).limit(100).with_for_update().all()
            if not jobs:
                return count
            for job in jobs:
                count += fail_unfinished(job, INTERRUPTED_MESSAGE)
            last_id = jobs[-1].id
            db.commit()
