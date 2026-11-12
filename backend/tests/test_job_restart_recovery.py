import asyncio
import threading
from pathlib import Path

import pytest

from app.main import app
from app.models import Job, JobStatus
from app.services import processing
from app.services.job_queue import JobQueue
from app.services.job_recovery import INTERRUPTED_MESSAGE, mark_failed, recover_interrupted_jobs


def uploaded_job(client):
    response = client.post('/upload', files=[
        ('files', (name, b'original-source', 'application/pdf')) for name in ('done.pdf', 'running.pdf', 'waiting.pdf')])
    assert response.status_code == 202
    return int(response.json()['jobId'])


@pytest.mark.parametrize('status', [JobStatus.PENDING, JobStatus.PROCESSING, JobStatus.TIMED_OUT])
def test_restart_fails_only_unfinished_work_and_is_idempotent(client, session_factory, status):
    job_id = uploaded_job(client)
    with session_factory() as db:
        job = db.get(Job, job_id)
        job.status = status
        first, second, third = job.job_files
        first.status = JobStatus.COMPLETED
        second.status = JobStatus.TIMED_OUT
        job.result_data = {'documents': {str(first.document_id): {'summary': 'Saved result'}}}
        original = dict(job.result_data)
        paths = [Path(file.document.storage_path) for file in job.job_files]
        db.commit()
    assert recover_interrupted_jobs(session_factory) == 1
    assert recover_interrupted_jobs(session_factory) == 0
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'failed' and saved['completed_count'] == 1
    assert saved['finished_at'] is not None and saved['result_data'] == original
    assert [file['status'] for file in saved['job_files']] == ['completed', 'failed', 'failed']
    assert saved['job_files'][0]['error_message'] is None
    assert all(file['error_message'] == INTERRUPTED_MESSAGE for file in saved['job_files'][1:])
    assert all(path.read_bytes() == b'original-source' for path in paths)


@pytest.mark.parametrize('terminal', [JobStatus.COMPLETED, JobStatus.FAILED])
def test_recovery_and_late_worker_failure_preserve_terminal_jobs(client, session_factory, terminal):
    job_id = uploaded_job(client)
    with session_factory() as db:
        job = db.get(Job, job_id)
        job.status = terminal
        db.commit()
    before = client.get(f'/jobs/{job_id}').json()
    assert recover_interrupted_jobs(session_factory) == 0
    mark_failed(job_id, session_factory, INTERRUPTED_MESSAGE)
    assert client.get(f'/jobs/{job_id}').json() == before


def test_lifespan_recovers_before_accepting_work(session_factory, monkeypatch, tmp_path):
    import app.main as main
    monkeypatch.setattr(main, 'SessionLocal', session_factory)
    monkeypatch.setattr(main.settings, 'STORAGE_DIR', tmp_path / 'uploads')
    with session_factory() as db:
        job = Job(owner_id=123, mode='bullet', status=JobStatus.PENDING, file_count=0)
        db.add(job)
        db.commit()
        job_id = job.id
    async def check():
        async with main.lifespan(app):
            with session_factory() as db:
                assert db.get(Job, job_id).status == JobStatus.FAILED
            assert not app.state.job_queue.tasks
    asyncio.run(check())


def test_queue_deduplicates_active_job_and_stops_accepting_at_close(session_factory):
    started, release = threading.Event(), threading.Event()
    calls = []
    def worker(job_id, factory):
        calls.append(job_id)
        started.set()
        release.wait(2)
    async def check():
        queue = JobQueue(session_factory, worker)
        first = queue.enqueue(42)
        assert queue.enqueue(42) is first
        await asyncio.to_thread(started.wait, 1)
        release.set()
        await queue.close()
        assert calls == [42]
        with pytest.raises(RuntimeError, match='shutting down'):
            queue.enqueue(42)
    asyncio.run(check())


def test_shutdown_cancels_real_worker_coroutine_and_retains_partial_results(client, session_factory, monkeypatch):
    job_id = uploaded_job(client)
    with session_factory() as db:
        job = db.get(Job, job_id)
        first = job.job_files[0]
        first.status = JobStatus.COMPLETED
        job.completed_count = 1
        job.result_data = {'documents': {str(first.document_id): {'summary': 'Saved result'}}}
        db.commit()
    started, cleaned = threading.Event(), threading.Event()
    async def blocked_extraction(*args, **kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()
    monkeypatch.setattr(processing, 'prepare_document', blocked_extraction)
    async def check():
        queue = JobQueue(session_factory, grace_seconds=.01, cleanup_seconds=2)
        queue.enqueue(job_id)
        assert await asyncio.to_thread(started.wait, 1)
        await queue.close()
        assert cleaned.is_set()
        assert not queue.tasks
    asyncio.run(check())
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'failed' and saved['completed_count'] == 1
    assert len(saved['result_data']['documents']) == 1
    assert [file['status'] for file in saved['job_files']] == ['completed', 'failed', 'failed']
    assert all('interrupted' in file['error_message'] for file in saved['job_files'][1:])


def test_late_analysis_cannot_overwrite_interruption_failure(client, session_factory):
    job_id = uploaded_job(client)
    async def analyzer(document, mode):
        mark_failed(job_id, session_factory, INTERRUPTED_MESSAGE)
        return {'summary': 'Late output must not be saved'}
    processing.process_job(job_id, session_factory, analyzer)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'failed'
    assert saved['completed_count'] == 0
    assert saved['result_data']['documents'] == {}
