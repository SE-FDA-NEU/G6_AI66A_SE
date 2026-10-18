import asyncio
import logging
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event

from app.models import Job, JobFile, JobStatus
from app.services import processing
from app.services.job_queue import JobQueue, get_job_queue
from app.main import app


def create_job(client, session_factory, page_counts):
    response = client.post('/upload', files=[
        ('files', (f'document-{i}.pdf', b'sample', 'application/pdf'))
        for i in range(len(page_counts))
    ])
    assert response.status_code == 202
    job_id = int(response.json()['jobId'])
    with session_factory() as db:
        job = db.get(Job, job_id)
        ids = []
        for link, pages in zip(job.job_files, page_counts):
            link.document.page_count = pages
            ids.append(link.document_id)
        db.commit()
    return job_id, ids


@pytest.mark.parametrize('pages, expected', [
    (None, 30), (0, 30), (1, 33), (15, 75), (89, 297),
    (90, 300), (91, 300), (1000, 300), (-1, 30),
])
def test_timeout_formula_and_cap(pages, expected):
    assert processing.document_timeout(pages) == expected


def test_always_timeout_retries_twice_and_persists_failure(client, session_factory, caplog):
    job_id, ids = create_job(client, session_factory, [15])
    processor = AsyncMock(side_effect=TimeoutError)
    transitions = []
    def record_flush(db, _):
        for item in db.identity_map.values():
            if isinstance(item, JobFile) and item in db.dirty:
                transitions.append((item.status, item.attempt_count))
    event.listen(session_factory.class_, 'after_flush', record_flush)
    try:
        with caplog.at_level(logging.INFO, logger=processing.__name__):
            processing.process_job(job_id, session_factory, processor)
    finally:
        event.remove(session_factory.class_, 'after_flush', record_flush)
    assert processor.await_count == 3
    assert all((JobStatus.TIMED_OUT, i) in transitions for i in (1, 2, 3))
    with session_factory() as db:
        job = db.get(Job, job_id)
        file = job.job_files[0]
        assert file.status == job.status == JobStatus.FAILED
        assert file.attempt_count == 3 and file.timeout_seconds == 75
        assert '3 attempts' in file.error_message
        assert job.completed_count == 0 and job.result_data['documents'] == {}
        assert job.finished_at is not None
    for i in (1, 2, 3):
        assert f'job={job_id} document={ids[0]} attempt={i}/3 timeout=75s started' in caplog.text
        assert f'attempt={i}/3 timed_out' in caplog.text


def test_third_attempt_can_succeed_and_clears_timeout_error(client, session_factory):
    job_id, ids = create_job(client, session_factory, [1])
    processor = AsyncMock(side_effect=[TimeoutError(), TimeoutError(), {'summary': 'real result'}])
    processing.process_job(job_id, session_factory, processor)
    with session_factory() as db:
        job = db.get(Job, job_id)
        file = job.job_files[0]
        assert job.status == file.status == JobStatus.COMPLETED
        assert file.attempt_count == 3 and file.timeout_seconds == 33
        assert file.error_message is None
        assert job.completed_count == 1
        assert job.result_data['documents'][str(ids[0])] == {'summary': 'real result'}


def test_timeout_does_not_skip_other_documents(client, session_factory):
    job_id, ids = create_job(client, session_factory, [1, 100])
    calls = []
    async def processor(document, mode):
        calls.append(document.id)
        if document.id == ids[0]:
            raise TimeoutError
        return {'summary': 'second document completed'}
    processing.process_job(job_id, session_factory, processor)
    assert calls == [ids[0], ids[0], ids[0], ids[1]]
    with session_factory() as db:
        job = db.get(Job, job_id)
        assert job.status == JobStatus.FAILED and job.completed_count == 1
        first, second = job.job_files
        assert first.status == JobStatus.FAILED and first.attempt_count == 3
        assert second.status == JobStatus.COMPLETED and second.attempt_count == 1
        assert [first.timeout_seconds, second.timeout_seconds] == [33, 300]


def test_actual_deadline_cancels_each_attempt_before_retry(client, session_factory, monkeypatch):
    job_id, _ = create_job(client, session_factory, [5])
    wait_for = asyncio.wait_for
    deadlines, cancelled = [], []
    running = 0
    async def short_deadline(coroutine, timeout):
        deadlines.append(timeout)
        return await wait_for(coroutine, timeout=0.01)
    async def hanging(document, mode):
        nonlocal running
        running += 1
        assert running == 1, 'A timed-out attempt is still running'
        try:
            await asyncio.Event().wait()
        finally:
            running -= 1
            cancelled.append(document.id)
    monkeypatch.setattr(processing.asyncio, 'wait_for', short_deadline)
    processing.process_job(job_id, session_factory, hanging)
    assert deadlines == [45, 45, 45]
    assert len(cancelled) == 3 and running == 0
    with session_factory() as db:
        assert db.get(Job, job_id).job_files[0].status == JobStatus.FAILED


def test_non_timeout_error_fails_once_without_leaking_details(client, session_factory):
    job_id, _ = create_job(client, session_factory, [1])
    processor = AsyncMock(side_effect=ValueError('private internal details'))
    processing.process_job(job_id, session_factory, processor)
    assert processor.await_count == 1
    with session_factory() as db:
        file = db.get(Job, job_id).job_files[0]
        assert file.status == JobStatus.FAILED and file.attempt_count == 1
        assert 'private internal details' not in file.error_message


def test_resuming_timed_out_file_does_not_reset_attempt_budget(client, session_factory):
    job_id, _ = create_job(client, session_factory, [1])
    with session_factory() as db:
        file = db.get(Job, job_id).job_files[0]
        file.status = JobStatus.TIMED_OUT
        file.attempt_count = 2
        db.commit()
    processor = AsyncMock(side_effect=TimeoutError)
    processing.process_job(job_id, session_factory, processor)
    assert processor.await_count == 1
    processing.process_job(job_id, session_factory, processor)
    assert processor.await_count == 1
    with session_factory() as db:
        assert db.get(Job, job_id).job_files[0].attempt_count == 3


def test_finished_files_are_skipped_on_resume(client, session_factory):
    job_id, _ = create_job(client, session_factory, [1, 1])
    with session_factory() as db:
        first = db.get(Job, job_id).job_files[0]
        first.status = JobStatus.COMPLETED
        first.attempt_count = 1
        db.commit()
    processor = AsyncMock(return_value=None)
    processing.process_job(job_id, session_factory, processor)
    assert processor.await_count == 1
    with session_factory() as db:
        job = db.get(Job, job_id)
        assert job.status == JobStatus.COMPLETED and job.completed_count == 2
        assert [file.attempt_count for file in job.job_files] == [1, 1]


def test_queue_uses_timeout_worker_and_job_poll_exposes_attempts(client, session_factory, monkeypatch):
    processor = AsyncMock(side_effect=TimeoutError)
    queue = JobQueue(session_factory, processor=lambda job_id, factory: processing.process_job(job_id, factory, processor))
    app.dependency_overrides[get_job_queue] = lambda: queue
    response = client.post('/upload', files=[('files', ('a.pdf', b'sample', 'application/pdf'))])
    assert response.status_code == 202
    client.portal.call(queue.close)
    job = client.get(f"/jobs/{response.json()['jobId']}").json()
    assert job['status'] == 'failed'
    assert job['job_files'][0]['status'] == 'failed'
    assert job['job_files'][0]['attempt_count'] == 3
    assert job['job_files'][0]['timeout_seconds'] == 30
    assert processor.await_count == 3
