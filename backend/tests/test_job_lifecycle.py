"""Lifecycle tests use real uploads, DB commits and the background job queue."""
import threading
from pathlib import Path
from unittest.mock import AsyncMock

from app.main import app
from app.models import Job, JobStatus
from app.services import processing
from app.services.job_queue import JobQueue, get_job_queue


def use_worker(session_factory, monkeypatch, processor):
    queue = JobQueue(session_factory, processor=lambda job_id, factory: processing.process_job(job_id, factory, processor))
    app.dependency_overrides[get_job_queue] = lambda: queue
    return queue


def test_submit_five_files_all_complete_and_results_persist_on_revisit(client, session_factory, monkeypatch):
    async def analyze(document, mode):
        assert Path(document.storage_path).read_bytes() == b'%PDF-1.4 mock input'
        return {'summary': f'Mock analysis for document {document.id}', 'mode': mode.value}

    processor = AsyncMock(side_effect=analyze)
    queue = use_worker(session_factory, monkeypatch, processor)
    try:
        response = client.post('/upload', data={'mode': 'bullet'}, files=[
            ('files', (f'contract-{i}.pdf', b'%PDF-1.4 mock input', 'application/pdf'))
            for i in range(1, 6)
        ])
        assert response.status_code == 202
    finally:
        client.portal.call(queue.close)

    job_id = int(response.json()['jobId'])
    response = client.get(f'/jobs/{job_id}')
    assert response.status_code == 200
    completed = response.json()
    assert completed['status'] == 'completed'
    assert completed['file_count'] == completed['completed_count'] == 5
    assert completed['finished_at'] is not None
    assert len(completed['job_files']) == processor.await_count == 5
    assert {file['original_filename'] for file in completed['job_files']} == {
        f'contract-{i}.pdf' for i in range(1, 6)
    }
    for file in completed['job_files']:
        assert file['status'] == 'completed'
        assert file['attempt_count'] == 1
        assert file['error_message'] is None
        result = completed['result_data']['documents'][str(file['document_id'])]
        assert result['summary'] == f"Mock analysis for document {file['document_id']}"
    with session_factory() as db:
        saved = db.get(Job, job_id)
        assert saved.status == JobStatus.COMPLETED
        assert saved.result_data == completed['result_data']

    # Reopening the resource uses a new request/session and must not reprocess it.
    revisited = client.get(f'/jobs/{job_id}')
    assert revisited.status_code == 200
    assert revisited.json() == completed
    processing.process_job(job_id, session_factory, processor)
    assert processor.await_count == 5
    assert client.get(f'/jobs/{job_id}').json() == completed


def test_mock_timeout_is_observable_before_retry_and_never_counts_as_success(client, session_factory, monkeypatch):
    timed_out, release_retry = threading.Event(), threading.Event()
    processor = AsyncMock(side_effect=TimeoutError)
    queue = use_worker(session_factory, monkeypatch, processor)
    original_warning = processing.logger.warning
    timeout_logs = []

    def observe_timeout(message, *args):
        original_warning(message, *args)
        timeout_logs.append(args)
        if not timed_out.is_set():
            # Pause AFTER the real worker commits timed_out, BEFORE its next attempt.
            timed_out.set()
            assert release_retry.wait(5), 'Test did not release the retry gate'

    monkeypatch.setattr(processing.logger, 'warning', observe_timeout)
    try:
        response = client.post('/upload', files=[('files', ('slow.pdf', b'%PDF-1.4 mock input', 'application/pdf'))])
        assert response.status_code == 202
        job_id = response.json()['jobId']
        assert timed_out.wait(2), 'Background worker did not reach its timeout'
        polled = client.get(f'/jobs/{job_id}')
        assert polled.status_code == 200
        retrying = polled.json()
        assert retrying['status'] == 'processing'
        assert retrying['completed_count'] == 0
        assert retrying['result_data'] is None and retrying['finished_at'] is None
        file = retrying['job_files'][0]
        assert file['status'] == 'timed_out'
        assert file['attempt_count'] == 1
        assert 'exceeded' in file['error_message']
    finally:
        release_retry.set()
        client.portal.call(queue.close)

    failed = client.get(f'/jobs/{job_id}').json()
    assert processor.await_count == len(timeout_logs) == 3
    assert failed['status'] == failed['job_files'][0]['status'] == 'failed'
    assert failed['job_files'][0]['attempt_count'] == 3
    assert failed['completed_count'] == 0 and failed['result_data'] is None
    assert failed['finished_at'] is not None
