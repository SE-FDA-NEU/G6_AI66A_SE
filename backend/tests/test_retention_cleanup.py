"""Temporary storage/SQLite only: never run cleanup against a developer's DB."""
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import threading

import pytest

from app.core.config import settings
from app.core.security import create_access_token
from app.models import Citation, Document, Job, JobStatus
from app.schemas.result import AnalysisResult, Claim, Evidence, TableOutput
from app.services import processing, retention_cleanup as cleanup
from app.services.reader_extraction import extract_document_for_reader, ReaderConversionError
from test_pdf_extraction import make_pdf

NOW = datetime(2026, 3, 25, 12)


@pytest.fixture
def corpus(client, session_factory, tmp_path, monkeypatch):
    monkeypatch.setattr(cleanup, 'utcnow', lambda: NOW)
    source = make_pdf(tmp_path / 'input.pdf', [b'BT /F1 12 Tf 30 720 Td (RetentionSecret 1,200,000,000 VND.) Tj ET'])
    uploaded = client.post('/upload', data={'mode': 'table'}, files=[
        ('files', (f'contract-{i}.pdf', source.read_bytes(), 'application/pdf')) for i in range(2)])
    assert uploaded.status_code == 202
    job_id = int(uploaded.json()['jobId'])

    async def analyze(document, mode):
        page = document.extracted_text[0]
        quote = page['text']
        claim = Claim(text='1,200,000,000 VND', unverified=False, evidence=[Evidence(
            document_id=document.id, page=1, start=0, end=len(quote), quote=quote,
            reader_version=page['reader']['sha256'])])
        return AnalysisResult(output=TableOutput(value=claim))

    processing.process_job(job_id, session_factory, analyzer=analyze)
    with session_factory() as db:
        job = db.get(Job, job_id)
        ids = [file.document_id for file in job.job_files]
        paths, readers, versions = {}, {}, {}
        for index, file in enumerate(job.job_files):
            doc = file.document
            doc.last_accessed_at = NOW - timedelta(days=31)
            doc.expires_at = NOW - timedelta(seconds=1) if index == 0 else max(NOW, datetime.utcnow()) + timedelta(days=30)
            paths[doc.id] = Path(doc.storage_path)
            readers[doc.id] = paths[doc.id].parent / '.reader' / str(doc.id)
            versions[doc.id] = doc.extracted_text[0]['reader']['sha256']
            (readers[doc.id] / 'old-version.pdf').write_bytes(b'old derived content')
        db.commit()
    return {'expired': ids[0], 'active': ids[1], 'job': job_id,
            'paths': paths, 'readers': readers, 'versions': versions}


def sweep(factory):
    return cleanup.cleanup_expired_documents(factory, now=NOW, batch_size=1)


def test_cleanup_removes_original_all_rendered_versions_search_caches_citations_and_saved_results(
        client, session_factory, corpus):
    ids = corpus
    assert sweep(session_factory) == {'deleted': 1, 'skipped': 0, 'retry': 0}
    assert not ids['paths'][ids['expired']].exists()
    assert not ids['readers'][ids['expired']].exists()
    assert ids['paths'][ids['active']].exists() and ids['readers'][ids['active']].exists()
    with session_factory() as db:
        doc = db.get(Document, ids['expired'])
        assert doc.extracted_text is None and doc.storage_path == '' and doc.file_size_bytes == 0
        assert doc.ai_label is doc.user_label is doc.ai_confidence is None
        assert db.query(Citation).filter_by(job_id=ids['job']).count() == 0
        job = db.get(Job, ids['job'])
        assert job.result_data is None and job.status == JobStatus.FAILED
    listed = client.get('/documents').json()
    assert [doc['id'] for doc in listed] == [ids['active']]
    search = client.get('/search?q=RetentionSecret').json()
    assert all(hit['document_id'] != ids['expired'] for hit in search['hits'])
    assert any(hit['document_id'] == ids['active'] for hit in search['hits'])
    result = client.get(f"/jobs/{ids['job']}").json()
    assert result['result_data'] is None and result['citations'] == []
    expired_file = next(file for file in result['job_files'] if file['document_id'] == ids['expired'])
    assert 'source_expired' in expired_file['error_message']
    assert client.get(f"/jobs/{ids['job']}/export.pdf").status_code == 409
    assert sweep(session_factory) == {'deleted': 0, 'skipped': 0, 'retry': 0}


@pytest.mark.parametrize('suffix,method,body', [('', 'get', None), ('/pages', 'get', None),
    ('/pages/1/text', 'get', None), ('/file', 'get', None), ('/file?rendered=true', 'get', None),
    ('/rendered-file', 'get', None), ('/reader.pdf?version=old', 'get', None),
    ('/reader', 'post', None), ('/label', 'patch', {'user_label': 'Restore'}),
    ('/folder', 'patch', {'folder_id': None})])
def test_old_document_urls_return_expired_without_content_or_resurrection(
        client, session_factory, corpus, suffix, method, body):
    sweep(session_factory)
    url = f"/documents/{corpus['expired']}{suffix}"
    response = getattr(client, method)(url, **({'json': body} if body else {}))
    assert response.status_code == 410 and response.json()['detail']['code'] == 'source_expired'
    assert 'RetentionSecret' not in response.text and '1,200,000,000' not in response.text
    denied = client.get(f"/documents/{corpus['expired']}/pages", headers={
        'Authorization': f"Bearer {create_access_token({'sub': '124'})}"})
    assert denied.status_code == 403
    with pytest.raises(ReaderConversionError, match='expired'):
        extract_document_for_reader(corpus['expired'], session_factory)


def test_renewal_between_candidate_selection_and_lock_preserves_files_and_results(
        client, session_factory, corpus, monkeypatch):
    real_claim = cleanup.cleanup_document
    entered, release = threading.Event(), threading.Event()
    failures = []

    def claim(*args):
        entered.set()
        assert release.wait(5)
        return real_claim(*args)
    monkeypatch.setattr(cleanup, 'cleanup_document', claim)

    def run():
        try:
            sweep(session_factory)
        except BaseException as error:
            failures.append(error)
    worker = threading.Thread(target=run)
    worker.start()
    try:
        assert entered.wait(5)
        # A real API update in another thread/session commits its renewal while
        # cleanup still holds only the stale candidate ID.
        response = client.patch(f"/documents/{corpus['expired']}/folder", json={'folder_id': None})
        assert response.status_code == 200
    finally:
        release.set(); worker.join(5)
    assert not worker.is_alive() and failures == []
    assert corpus['paths'][corpus['expired']].exists() and corpus['readers'][corpus['expired']].exists()
    assert client.get(f"/jobs/{corpus['job']}").json()['result_data'] is not None


def test_failed_file_deletion_is_private_retryable_and_does_not_starve_other_candidates(
        client, session_factory, corpus, monkeypatch):
    original_remove = cleanup._remove_files
    with session_factory() as db:
        db.get(Document, corpus['active']).expires_at = NOW
        db.commit()
    def remove(db, doc, root):
        if doc.id == corpus['expired']:
            raise PermissionError('locked file')
        return original_remove(db, doc, root)
    monkeypatch.setattr(cleanup, '_remove_files', remove)
    assert sweep(session_factory) == {'deleted': 1, 'skipped': 0, 'retry': 1}
    assert client.get(f"/documents/{corpus['expired']}/file").status_code == 410
    with session_factory() as db:
        doc = db.get(Document, corpus['expired'])
        assert doc.extracted_text is None and doc.storage_path
    monkeypatch.setattr(cleanup, '_remove_files', original_remove)
    assert sweep(session_factory) == {'deleted': 1, 'skipped': 0, 'retry': 0}


def test_cleanup_never_unlinks_outside_storage(client, session_factory, corpus, tmp_path):
    outside = tmp_path / 'do-not-delete.pdf'
    outside.write_bytes(b'private outside storage')
    with session_factory() as db:
        db.get(Document, corpus['expired']).storage_path = str(outside)
        db.commit()
    assert sweep(session_factory)['retry'] == 1
    assert outside.read_bytes() == b'private outside storage'
    assert client.get(f"/documents/{corpus['expired']}/file").status_code == 410


def test_optional_shared_model_cache_is_purged_only_for_the_expired_owner(
        client, session_factory, corpus):
    cache = settings.STORAGE_DIR / '.analysis-cache'
    for owner in (123, 124):
        (cache / str(owner)).mkdir(parents=True)
        (cache / str(owner) / 'result.json').write_text('sensitive cached analysis')
    sweep(session_factory)
    assert not (cache / '123' / 'result.json').exists()
    assert (cache / '124' / 'result.json').exists()
    # A late model write after expiration is removed on the next sweep too.
    (cache / '123' / 'late.json').write_text('late expired response')
    sweep(session_factory)
    assert not (cache / '123' / 'late.json').exists()


def test_zero_byte_document_is_not_itself_an_expiry_marker(client, session_factory, corpus):
    with session_factory() as db:
        db.get(Document, corpus['active']).file_size_bytes = 0
        db.commit()
    assert client.get(f"/documents/{corpus['active']}").status_code == 200
    assert any(doc['id'] == corpus['active'] for doc in client.get('/documents').json())


def test_app_lifespan_starts_and_stops_the_enabled_scheduler(session_factory, monkeypatch):
    import app.main as main
    events = []
    class Scheduler:
        def __init__(self, factory):
            assert factory is session_factory
        def start(self):
            events.append('start')
        async def close(self):
            events.append('close')
    monkeypatch.setattr(main, 'SessionLocal', session_factory)
    monkeypatch.setattr(main, 'RetentionCleanupScheduler', Scheduler)
    monkeypatch.setattr(settings, 'RETENTION_CLEANUP_ENABLED', True)
    async def check():
        async with main.lifespan(main.app):
            assert events == ['start']
        assert events == ['start', 'close']
    asyncio.run(check())


def test_cleanup_rejects_linked_rendered_files(client, session_factory, corpus, tmp_path):
    outside = tmp_path / 'outside.txt'
    outside.write_text('keep me')
    link = corpus['readers'][corpus['expired']] / 'escape.pdf'
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip('Creating symlinks requires Windows developer mode or symlink privileges')
    assert sweep(session_factory)['retry'] == 1
    assert outside.read_text() == 'keep me' and corpus['paths'][corpus['expired']].exists()


def test_scheduler_retries_after_failure_and_stops_gracefully(monkeypatch):
    calls = []
    def run(factory):
        calls.append(factory)
        if len(calls) == 1:
            raise OSError('temporary failure')
        return {'deleted': 0}
    monkeypatch.setattr(cleanup, 'cleanup_expired_documents', run)
    async def check():
        scheduler = cleanup.RetentionCleanupScheduler('isolated', interval=.01)
        scheduler.start()
        for _ in range(100):
            if len(calls) >= 2:
                break
            await asyncio.sleep(.01)
        await scheduler.close()
        assert scheduler.task.done() and len(calls) >= 2
    asyncio.run(check())


def test_analysis_finishing_after_cleanup_cannot_restore_pages_files_or_results(
        client, session_factory, corpus):
    with session_factory() as db:
        job = db.get(Job, corpus['job'])
        job.status = JobStatus.PENDING
        for file in job.job_files:
            if file.document_id == corpus['expired']:
                file.status = JobStatus.PENDING
                file.attempt_count = 0
        db.commit()

    async def late_result(document, mode):
        # The model has already received its source; cleanup wins before the
        # asynchronous answer returns to the persistence transaction.
        assert document.extracted_text
        assert cleanup.cleanup_document(session_factory, document.id, NOW, settings.STORAGE_DIR) == 'deleted'
        return AnalysisResult(output=TableOutput())

    processing.process_job(corpus['job'], session_factory, analyzer=late_result)
    saved = client.get(f"/jobs/{corpus['job']}").json()
    assert saved['status'] == 'failed' and saved['result_data'] is None and saved['citations'] == []
    assert not corpus['paths'][corpus['expired']].exists()
    assert not corpus['readers'][corpus['expired']].exists()
    with session_factory() as db:
        assert db.get(Document, corpus['expired']).extracted_text is None


def test_active_document_analysis_cannot_reintroduce_a_claim_from_an_expired_cross_document_source(
        client, session_factory, corpus):
    with session_factory() as db:
        old_claim = db.get(Job, corpus['job']).result_data['documents'][str(corpus['expired'])]['output']['value']
    sweep(session_factory)
    with session_factory() as db:
        job = db.get(Job, corpus['job'])
        job.status = JobStatus.PENDING
        for file in job.job_files:
            if file.document_id == corpus['active']:
                file.status = JobStatus.PENDING
                file.attempt_count = 0
        db.commit()
    async def stale_claim(document, mode):
        return AnalysisResult(output=TableOutput(value=Claim.model_validate(old_claim)))
    processing.process_job(corpus['job'], session_factory, analyzer=stale_claim)
    saved = client.get(f"/jobs/{corpus['job']}").json()
    assert saved['result_data'] is None and saved['citations'] == []
    assert corpus['paths'][corpus['active']].exists()
