import threading
from pathlib import Path

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.models import Document, Folder, Job, JobFile, JobMode, JobStatus
from app.services import uploads
from app.services.job_queue import JobQueue, get_job_queue


def parts(*names):
    return [('files', (name, f'contents:{name}'.encode(), 'application/octet-stream')) for name in names]


def assert_empty(session_factory, job_queue):
    with session_factory() as db:
        for model in (Job, JobFile, Document):
            assert db.query(model).count() == 0
    assert job_queue.enqueued == []
    assert not list(settings.STORAGE_DIR.rglob('*.*'))


def test_upload_destination_is_committed_before_enqueue_and_survives_processing(client, session_factory, job_queue, monkeypatch):
    from app.services.processing import process_job
    with session_factory() as db:
        folder = Folder(owner_id=123, name='Research')
        db.add(folder); db.commit()
        folder_id = folder.id
    enqueue = job_queue.enqueue
    def inspect_committed_destination(job_id):
        with session_factory() as db:
            job = db.get(Job, job_id)
            assert job.status == JobStatus.PENDING
            assert len(job.job_files) == 2
            assert all(link.document.folder_id == folder_id for link in job.job_files)
        enqueue(job_id)
    monkeypatch.setattr(job_queue, 'enqueue', inspect_committed_destination)
    response = client.post('/upload', files=parts('first.pdf', 'second.pdf'), data={'folder_id': folder_id})
    assert response.status_code == 202
    job_id = int(response.json()['jobId'])
    assert job_queue.enqueued == [job_id]
    async def processor(source, mode):
        return {'text': 'Saved summary'}
    process_job(job_id, session_factory, processor=processor)
    assert client.get(f'/jobs/{job_id}').json()['status'] == 'completed'
    with session_factory() as db:
        assert all(doc.folder_id == folder_id for doc in db.query(Document).all())
    assert len(client.get('/documents', params={'folder_id': folder_id}).json()) == 2
    assert client.get('/documents', params={'unassigned': 'true'}).json() == []


def test_upload_without_destination_stays_outside_existing_folders(client, session_factory):
    with session_factory() as db:
        db.add(Folder(owner_id=123, name='Existing folder')); db.commit()
    assert client.post('/upload', files=parts('outside.pdf')).status_code == 202
    with session_factory() as db:
        assert db.query(Document).one().folder_id is None


@pytest.mark.parametrize('destination,status', [('missing', 404), ('foreign', 403)])
def test_invalid_destination_writes_no_files_or_jobs(client, session_factory, job_queue, destination, status):
    folder_id = 99999
    if destination == 'foreign':
        with session_factory() as db:
            folder = Folder(owner_id=124, name='Private folder')
            db.add(folder); db.commit(); folder_id = folder.id
    response = client.post('/upload', files=parts('a.pdf'), data={'folder_id': folder_id})
    assert response.status_code == status
    assert_empty(session_factory, job_queue)


@pytest.mark.parametrize('folder_id', ['0', '-1', 'invalid', '1.5'])
def test_malformed_upload_destination_is_rejected(client, session_factory, job_queue, folder_id):
    assert client.post('/upload', files=parts('a.pdf'), data={'folder_id': folder_id}).status_code == 422
    assert_empty(session_factory, job_queue)


@pytest.mark.parametrize('mode', ['bullet', 'table', 'concept'])
def test_saved_batch_has_pending_job_documents_and_links(client, session_factory, job_queue, mode):
    response = client.post('/upload', files=parts('contract.pdf', 'notes.docx', 'slides.pptx'), data={'mode': mode})
    assert response.status_code == 202
    assert set(response.json()) == {'jobId'}
    job_id = int(response.json()['jobId'])
    assert job_queue.enqueued == [job_id]
    with session_factory() as db:
        job = db.get(Job, job_id)
        assert job.owner_id == 123
        assert job.mode == JobMode(mode)
        assert job.status == JobStatus.PENDING
        assert job.file_count == 3 and job.completed_count == 0
        assert len(job.job_files) == 3
        for link in job.job_files:
            doc = link.document
            assert link.status == JobStatus.PENDING
            assert doc.owner_id == 123
            assert doc.folder_id is None
            assert (doc.expires_at - doc.last_accessed_at).days == 30
            content = f'contents:{doc.original_filename}'.encode()
            assert doc.file_size_bytes == len(content)
            assert Path(doc.storage_path).read_bytes() == content
    polled = client.get(f'/jobs/{job_id}').json()
    assert polled['status'] == 'pending'
    assert {file['original_filename'] for file in polled['job_files']} == {'contract.pdf', 'notes.docx', 'slides.pptx'}
    other = f"Bearer {create_access_token({'sub': '124'})}"
    assert client.get(f'/jobs/{job_id}', headers={'Authorization': other}).status_code == 404


def test_duplicate_and_path_like_names_never_control_storage_paths(client, session_factory):
    response = client.post('/upload', files=parts('../../report.pdf', 'report.pdf', '..\\report.pdf'))
    assert response.status_code == 202
    with session_factory() as db:
        documents = db.query(Document).all()
        paths = [Path(doc.storage_path) for doc in documents]
        assert len(set(paths)) == 3
        assert all(path.is_relative_to(settings.STORAGE_DIR.resolve()) for path in paths)
        assert all(doc.original_filename == 'report.pdf' for doc in documents)
        assert all(path.name != 'report.pdf' for path in paths)


@pytest.mark.parametrize('mode', ['BULLET', 'unsupported'])
def test_invalid_mode_has_no_side_effects(client, session_factory, job_queue, mode):
    response = client.post('/upload', files=parts('a.pdf'), data={'mode': mode})
    assert response.status_code == 422
    assert_empty(session_factory, job_queue)


def test_invalid_batch_has_no_side_effects(client, session_factory, job_queue):
    assert client.post('/upload', files=parts('a.pdf', 'bad.exe')).status_code == 422
    assert_empty(session_factory, job_queue)


def test_deleted_account_cannot_create_job(client, session_factory, job_queue):
    header = f"Bearer {create_access_token({'sub': '99999'})}"
    response = client.post('/upload', files=parts('a.pdf'), headers={'Authorization': header})
    assert response.status_code == 401
    assert_empty(session_factory, job_queue)


def test_partial_storage_failure_rolls_back_only_new_batch(client, session_factory, job_queue, monkeypatch):
    assert client.post('/upload', files=parts('existing.pdf')).status_code == 202
    with session_factory() as db:
        previous = Path(db.query(Document).one().storage_path)
    copy = uploads.shutil.copyfileobj
    calls = 0
    def fail_second(source, destination, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            destination.write(b'partial')
            raise OSError('simulated disk full')
        return copy(source, destination, **kwargs)
    monkeypatch.setattr(uploads.shutil, 'copyfileobj', fail_second)
    response = client.post('/upload', files=parts('a.pdf', 'b.pdf'))
    assert response.status_code == 500
    assert 'simulated' not in response.text
    with session_factory() as db:
        assert db.query(Job).count() == db.query(JobFile).count() == db.query(Document).count() == 1
    assert previous.read_bytes() == b'contents:existing.pdf'
    assert list(settings.STORAGE_DIR.rglob('*.pdf')) == [previous]
    assert len(job_queue.enqueued) == 1


def test_database_failure_removes_saved_files(client, session_factory, job_queue, monkeypatch):
    def fail_commit(_):
        raise SQLAlchemyError('simulated database failure')
    monkeypatch.setattr(session_factory.class_, 'commit', fail_commit)
    assert client.post('/upload', files=parts('a.pdf')).status_code == 500
    assert_empty(session_factory, job_queue)


def test_existing_batch_directory_is_never_deleted(client, session_factory, job_queue, monkeypatch):
    class FixedId:
        hex = 'existing-batch'
    directory = settings.STORAGE_DIR / '123' / FixedId.hex
    directory.mkdir(parents=True)
    previous = directory / 'existing.pdf'
    previous.write_bytes(b'preserve existing data')
    monkeypatch.setattr(uploads, 'uuid4', FixedId)
    assert client.post('/upload', files=parts('a.pdf')).status_code == 500
    assert previous.read_bytes() == b'preserve existing data'
    with session_factory() as db:
        assert db.query(Job).count() == db.query(Document).count() == 0
    assert job_queue.enqueued == []


def test_queue_failure_is_recorded_instead_of_leaving_pending_job(client, session_factory, job_queue, monkeypatch):
    def unavailable(_):
        raise RuntimeError('queue unavailable')
    monkeypatch.setattr(job_queue, 'enqueue', unavailable)
    response = client.post('/upload', files=parts('a.pdf'))
    assert response.status_code == 503
    with session_factory() as db:
        job = db.query(Job).one()
        assert job.status == JobStatus.FAILED
        assert job.finished_at is not None
        assert job.job_files[0].status == JobStatus.FAILED


def test_response_returns_while_real_background_worker_is_blocked(client, session_factory):
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    def worker(job_id, factory):
        with factory() as db:
            job = db.get(Job, job_id)
            assert job.status == JobStatus.PENDING
            assert Path(job.job_files[0].document.storage_path).read_bytes() == b'contents:a.pdf'
        started.set()
        assert release.wait(5), 'Response waited for processing instead of returning'
        finished.set()
    queue = JobQueue(session_factory, processor=worker)
    app.dependency_overrides[get_job_queue] = lambda: queue
    try:
        response = client.post('/upload', files=parts('a.pdf'))
        assert response.status_code == 202
        assert started.wait(2)
        assert not finished.is_set()
        # A second HTTP request also works while processing is blocked.
        assert client.get(f"/jobs/{response.json()['jobId']}").status_code == 200
        assert not finished.is_set()
    finally:
        release.set()
        client.portal.call(queue.close)
    assert finished.is_set()
    assert not queue.tasks


def test_worker_exception_is_recorded(client, session_factory):
    def worker(*_):
        raise RuntimeError('private internal error')
    queue = JobQueue(session_factory, processor=worker)
    app.dependency_overrides[get_job_queue] = lambda: queue
    response = client.post('/upload', files=parts('a.pdf'))
    assert response.status_code == 202
    client.portal.call(queue.close)
    with session_factory() as db:
        job = db.get(Job, int(response.json()['jobId']))
        assert job.status == JobStatus.FAILED
        assert 'private internal error' not in job.job_files[0].error_message
        assert job.finished_at is not None


def test_worker_crash_preserves_completed_results_and_fails_unfinished_files(client, session_factory):
    """TC-US07-007: a queue crash retains partial results without false completion."""
    def worker(job_id, factory):
        with factory() as db:
            job = db.get(Job, job_id)
            first, second, _ = job.job_files
            first.status = JobStatus.COMPLETED
            first.attempt_count = 1
            second.status = JobStatus.PROCESSING
            second.attempt_count = 1
            job.status = JobStatus.PROCESSING
            job.completed_count = 1
            job.result_data = {'documents': {str(first.document_id): {'summary': 'Saved result'}}}
            db.commit()
        raise RuntimeError('private worker crash')

    queue = JobQueue(session_factory, processor=worker)
    app.dependency_overrides[get_job_queue] = lambda: queue
    try:
        response = client.post('/upload', files=parts('done.pdf', 'running.pdf', 'pending.pdf'))
        assert response.status_code == 202
    finally:
        client.portal.call(queue.close)

    job_id = response.json()['jobId']
    polled = client.get(f'/jobs/{job_id}')
    assert polled.status_code == 200
    saved = polled.json()
    first, second, third = saved['job_files']
    assert saved['status'] == 'failed' and saved['finished_at'] is not None
    assert saved['file_count'] == 3 and saved['completed_count'] == 1
    assert [file['status'] for file in saved['job_files']] == ['completed', 'failed', 'failed']
    assert [file['attempt_count'] for file in saved['job_files']] == [1, 1, 0]
    assert first['error_message'] is None
    assert second['error_message'] == third['error_message'] == 'Background processing failed. Please retry.'
    assert saved['result_data']['documents'] == {str(first['document_id']): {'summary': 'Saved result'}}
    assert 'private worker crash' not in polled.text
    assert not queue.tasks
    assert client.get(f'/jobs/{job_id}').json() == saved


def test_default_worker_reports_invalid_pdf_extraction(client, session_factory):
    queue = JobQueue(session_factory)
    app.dependency_overrides[get_job_queue] = lambda: queue
    response = client.post('/upload', files=parts('a.pdf'))
    assert response.status_code == 202
    client.portal.call(queue.close)
    with session_factory() as db:
        job = db.get(Job, int(response.json()['jobId']))
        assert job.mode == JobMode.BULLET
        assert job.status == JobStatus.FAILED
        assert job.completed_count == 0 and job.result_data == {'schema_version': 1, 'language': 'vi', 'documents': {}}
        assert 'invalid_rendered_pdf' in job.job_files[0].error_message


def test_closed_queue_rejects_new_work(client, session_factory):
    queue = JobQueue(session_factory)
    client.portal.call(queue.close)
    with pytest.raises(RuntimeError, match='shutting down'):
        client.portal.call(queue.enqueue, 123)


@pytest.mark.parametrize('language', ['en', 'vi'])
def test_upload_language_is_saved_before_enqueue_and_passed_to_worker(client, session_factory, job_queue, language):
    from app.services.processing import process_job
    response = client.post('/upload', files=parts('language.pdf'), data={'language': language})
    assert response.status_code == 202
    job_id = int(response.json()['jobId'])
    with session_factory() as db:
        assert db.get(Job, job_id).result_data['language'] == language
    seen = []
    async def processor(source, mode):
        seen.append(source.language)
        return {'text': 'Saved summary'}
    process_job(job_id, session_factory, processor=processor)
    assert seen == [language]
    result = client.get(f'/jobs/{job_id}', headers={'X-DocuMind-Language': 'vi' if language == 'en' else 'en'})
    assert result.json()['result_data']['language'] == language
    with session_factory() as db:
        assert db.get(Job, job_id).result_data['language'] == language


def test_invalid_summary_language_does_not_create_upload(client, session_factory, job_queue):
    assert client.post('/upload', files=parts('a.pdf'), data={'language': 'fr'}).status_code == 422
    assert_empty(session_factory, job_queue)
