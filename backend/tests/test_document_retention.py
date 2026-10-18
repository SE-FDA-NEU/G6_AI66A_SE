"""Successful document activity renews 30 days; passive/failed requests never do."""
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.responses import FileResponse

from app.core.security import create_access_token
from app.models import Document, FileFormat, Folder, Job, JobFile, JobMode, JobStatus
from app.services import document_retention as retention
from app.services.reader_extraction import extract_document_for_reader, ReaderConversionError
from test_pdf_extraction import make_pdf
from test_financial_table import financial_batch
from test_table_pdf import completed_table


ACCESSED = datetime(2026, 3, 25, 10, 11, 12, 123456)
EXPIRES = datetime(2026, 4, 24, 10, 11, 12, 123456)
OLD = (datetime(2026, 3, 1), datetime(2026, 3, 31))


@pytest.fixture
def clock(monkeypatch):
    state = {'now': ACCESSED, 'calls': 0}
    def now():
        state['calls'] += 1
        return state['now']
    monkeypatch.setattr(retention, 'utcnow', now)
    return state


@pytest.fixture
def retained_documents(session_factory, tmp_path):
    source = make_pdf(tmp_path / 'contract.pdf', [b'BT /F1 12 Tf 30 720 Td (Payment 1,200,000,000 VND.) Tj ET'])
    ids = []
    with session_factory() as db:
        folder = Folder(owner_id=123, name='Research')
        private = Folder(owner_id=124, name='Private')
        db.add_all([folder, private]); db.flush()
        folder_ids = folder.id, private.id
        for owner in (123, 123, 124):
            doc = Document(owner_id=owner, original_filename='contract.pdf', storage_path=str(source),
                           file_format=FileFormat.PDF, file_size_bytes=source.stat().st_size,
                           ai_label='Contract', ai_confidence=.9,
                           last_accessed_at=OLD[0], expires_at=OLD[1])
            db.add(doc); db.flush(); ids.append(doc.id)
        job = Job(owner_id=123, mode=JobMode.TABLE, status=JobStatus.PROCESSING,
                  file_count=2, completed_count=0)
        db.add(job); db.flush()
        for doc_id in ids[:2]:
            db.add(JobFile(job_id=job.id, document_id=doc_id, status=JobStatus.PENDING))
        job_id = job.id
        db.commit()
    for doc_id in ids:
        extract_document_for_reader(doc_id, session_factory)
    return {'own': ids[0], 'other_own': ids[1], 'foreign': ids[2],
            'folder': folder_ids[0], 'foreign_folder': folder_ids[1], 'job': job_id, 'source': source}


def timestamps(factory, doc_id):
    with factory() as db:
        doc = db.get(Document, doc_id)
        return doc.last_accessed_at, doc.expires_at


@pytest.mark.parametrize('operation', ['metadata', 'pages', 'page_text', 'prepare', 'original',
                                       'rendered', 'rendered_alias', 'reader_pdf', 'range', 'label',
                                       'confirm', 'move', 'unfile'])
def test_successful_open_download_or_update_renews_exactly_30_days(
        client, session_factory, retained_documents, clock, operation):
    ids = retained_documents
    doc_id = ids['own']
    base = f'/documents/{doc_id}'
    if operation == 'metadata':
        response = client.get(base)
    elif operation == 'pages':
        response = client.get(base + '/pages')
    elif operation == 'page_text':
        response = client.get(base + '/pages/1/text')
    elif operation == 'prepare':
        response = client.post(base + '/reader')
    elif operation == 'original':
        response = client.get(base + '/file')
    elif operation == 'rendered':
        response = client.get(base + '/file?rendered=true')
    elif operation == 'rendered_alias':
        response = client.get(base + '/rendered-file')
    elif operation == 'reader_pdf':
        with session_factory() as db:
            version = db.get(Document, doc_id).extracted_text[0]['reader']['sha256']
        response = client.get(base + f'/reader.pdf?version={version}')
    elif operation == 'range':
        response = client.get(base + '/file', headers={'Range': 'bytes=0-15'})
    elif operation == 'label':
        response = client.patch(base + '/label', json={'user_label': 'Confirmed contract'})
    elif operation == 'confirm':
        response = client.patch(base + '/label', json={'review_state': 'confirmed'})
    else:
        response = client.patch(base + '/folder', json={'folder_id': ids['folder'] if operation == 'move' else None})
    assert response.status_code == (206 if operation == 'range' else 200), response.text[:200]
    assert timestamps(session_factory, doc_id) == (ACCESSED, EXPIRES)
    assert EXPIRES - ACCESSED == timedelta(days=30) and clock['calls'] == 1
    for untouched in (ids['other_own'], ids['foreign']):
        assert timestamps(session_factory, untouched) == OLD


def test_each_explicit_access_renews_from_the_new_access_not_the_old_expiry(
        client, session_factory, retained_documents, clock):
    doc_id = retained_documents['own']
    assert client.get(f'/documents/{doc_id}').status_code == 200
    clock['now'] = datetime(2026, 3, 26, 14, 30)
    assert client.patch(f'/documents/{doc_id}/folder', json={'folder_id': None}).status_code == 200
    assert timestamps(session_factory, doc_id) == (clock['now'], datetime(2026, 4, 25, 14, 30))


def test_workspace_search_and_job_polling_never_renew_documents(client, session_factory, retained_documents, clock):
    ids = retained_documents
    for _ in range(2):
        for url in ('/documents', '/documents?skip=1&limit=1', '/folders', '/jobs',
                    f"/jobs/{ids['job']}", '/search?q=Payment'):
            assert client.get(url).status_code == 200
    assert clock['calls'] == 0
    for doc_id in (ids['own'], ids['other_own'], ids['foreign']):
        assert timestamps(session_factory, doc_id) == OLD


@pytest.mark.parametrize('failure', ['ownership_open', 'ownership_download', 'ownership_label', 'ownership_folder',
                                    'invalid_label', 'missing_folder', 'foreign_folder', 'invalid_page',
                                    'missing_page', 'wrong_version', 'missing_file', 'bad_range', 'outside_range',
                                    'conversion', 'unauthenticated'])
def test_failed_requests_do_not_renew(client, session_factory, retained_documents, clock, monkeypatch, failure):
    ids = retained_documents
    base = f"/documents/{ids['own']}"
    if failure.startswith('ownership'):
        base = f"/documents/{ids['foreign']}"
        if failure.endswith('open'):
            response = client.get(base + '/pages')
        elif failure.endswith('download'):
            response = client.get(base + '/file')
        elif failure.endswith('label'):
            response = client.patch(base + '/label', json={'user_label': 'Intrusion'})
        else:
            response = client.patch(base + '/folder', json={'folder_id': None})
    elif failure == 'invalid_label':
        response = client.patch(base + '/label', json={'user_label': ''})
    elif failure in ('missing_folder', 'foreign_folder'):
        response = client.patch(base + '/folder', json={'folder_id': ids['foreign_folder'] if failure == 'foreign_folder' else 999999})
    elif failure == 'invalid_page':
        response = client.get(base + '/file?page=999')
    elif failure == 'missing_page':
        response = client.get(base + '/pages/999/text')
    elif failure == 'wrong_version':
        response = client.get(base + '/reader.pdf?version=wrong')
    elif failure == 'missing_file':
        Path(ids['source']).unlink()
        response = client.get(base + '/file')
    elif failure in ('bad_range', 'outside_range'):
        response = client.get(base + '/file', headers={'Range': 'bytes=invalid' if failure == 'bad_range' else 'bytes=99999999-'})
    elif failure == 'conversion':
        def fail(*args):
            raise ReaderConversionError('conversion_failed', 'No reader produced.')
        monkeypatch.setattr('app.api.document.extract_document_for_reader', fail)
        response = client.post(base + '/reader')
    else:
        response = client.get(base, headers={'Authorization': 'Bearer invalid'})
    assert 400 <= response.status_code < 500
    assert clock['calls'] == 0
    for doc_id in (ids['own'], ids['other_own'], ids['foreign']):
        assert timestamps(session_factory, doc_id) == OLD


def test_stream_failure_after_headers_does_not_renew(client, session_factory, retained_documents, clock, monkeypatch):
    async def broken_stream(self, send, *args):
        await send({'type': 'http.response.start', 'status': 200, 'headers': self.raw_headers})
        raise OSError('Transfer failed before the final body.')
    monkeypatch.setattr(FileResponse, '_handle_simple', broken_stream)
    with pytest.raises(OSError):
        client.get(f"/documents/{retained_documents['own']}/file")
    assert timestamps(session_factory, retained_documents['own']) == OLD and clock['calls'] == 0


@pytest.mark.parametrize('operation', ['success', 'not_completed', 'foreign', 'render_failure'])
def test_comparison_pdf_download_renews_only_its_source_documents_after_success(
        client, session_factory, completed_table, retained_documents, clock, monkeypatch, operation):
    job_id, _ = completed_table
    with session_factory() as db:
        job = db.get(Job, job_id)
        doc_ids = [file.document_id for file in job.job_files]
        for file in job.job_files:
            file.document.last_accessed_at, file.document.expires_at = OLD
        if operation == 'not_completed':
            job.status = JobStatus.PROCESSING
        db.commit()
    if operation == 'foreign':
        client.headers['Authorization'] = f"Bearer {create_access_token({'sub': '124'})}"
    if operation == 'render_failure':
        def fail(*args):
            raise RuntimeError('PDF generation failed.')
        monkeypatch.setattr('app.api.job.render_table_pdf', fail)
        with pytest.raises(RuntimeError, match='PDF generation failed'):
            client.get(f'/jobs/{job_id}/export.pdf')
    else:
        response = client.get(f'/jobs/{job_id}/export.pdf')
        assert response.status_code == {'success': 200, 'not_completed': 409, 'foreign': 404}[operation]
    for doc_id in doc_ids:
        assert timestamps(session_factory, doc_id) == ((ACCESSED, EXPIRES) if operation == 'success' else OLD)
    assert clock['calls'] == (1 if operation == 'success' else 0)
    assert timestamps(session_factory, retained_documents['own']) == OLD
