"""Real uploads -> extraction -> existing job/result/citation persistence."""
import asyncio
import json
from pathlib import Path
import sys
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.database import Base
from app.main import app
from app.models import Document, FileFormat, Folder, Job, JobFile, JobStatus, ReviewState, User
from app.schemas.result import JobResultData
from app.services import job_extraction, processing
from app.services.job_queue import JobQueue, get_job_queue
from app.services.pdf_extraction import extract_pdf
from test_pdf_extraction import make_pdf
from test_reader_extraction import sources  # actual DOCX/PPTX fixtures, not extraction mocks


def upload(client, tmp_path, mode='bullet', count=1):
    source = make_pdf(tmp_path / 'input.pdf', [
        b'BT /F1 12 Tf 72 720 Td (Contract alpha) Tj ET', b'',
        b'BT /F1 12 Tf 72 720 Td (Late fee 0.05% per day.) Tj ET',
    ])
    response = client.post('/upload', data={'mode': mode}, files=[
        ('files', (f'contract-{i}.pdf', source.read_bytes(), 'application/pdf')) for i in range(count)
    ])
    assert response.status_code == 202
    return int(response.json()['jobId'])


def analysis(document, mode, confidence=.72, mutation=None):
    page = document.extracted_text[2]
    evidence = {'document_id': document.id, 'page': 3, 'start': 0, 'end': len(page['text']),
                'quote': page['text'], 'reader_version': page['reader']['sha256']}
    if mutation:
        mutation(evidence)
    claim = {'text': '0.05% per day', 'evidence': [evidence], 'unverified': False}
    if mode.value == 'bullet':
        output = {'type': 'bullet', 'bullets': [claim],
                  'actions': [{'text': 'Unsupported recommendation', 'unverified': False}]}
    elif mode.value == 'table':
        output = {'type': 'table', 'penalty': claim}
    else:
        output = {'type': 'concept', 'concepts': [{'name': 'Late fee', 'description': claim}]}
    return {'output': output, 'label': {'ai_label': 'Contract', 'ai_confidence': confidence}}


@pytest.mark.parametrize('mode', ['bullet', 'table', 'concept'])
def test_real_queue_extracts_five_documents_and_revisit_keeps_results(client, session_factory, tmp_path, mode):
    queue = JobQueue(session_factory)
    app.dependency_overrides[get_job_queue] = lambda: queue
    try:
        job_id = upload(client, tmp_path, mode, count=5)
    finally:
        client.portal.call(queue.close)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'completed'
    assert saved['completed_count'] == saved['file_count'] == 5
    JobResultData.model_validate(saved['result_data'])
    for file in saved['job_files']:
        assert file['status'] == 'completed' and file['attempt_count'] == 1
        assert file['timeout_seconds'] == 39  # actual extracted physical pages
        doc_id = file['document_id']
        result = saved['result_data']['documents'][str(doc_id)]
        assert result['mode'] == result['output']['type'] == mode
        assert result['analysis_status'] == 'not_configured'
        assert result['label']['ai_label'] is None
        assert result['label']['review_state'] == 'needs_review'
        assert result['label']['confidence_level'] == 'unknown'
        pages = client.get(f'/documents/{doc_id}/pages').json()
        assert pages['page_count'] == result['reader']['page_count'] == 3
        assert pages['pages'][1]['text'] == ''
        assert pages['reader_version'] == result['reader']['version']
        assert client.get(result['reader']['url']).status_code == 200
        with session_factory() as db:
            document = db.get(Document, doc_id)
            assert document.page_count == 3 and document.extracted_text == pages['pages']
    processing.process_job(job_id, session_factory)  # terminal jobs must not re-run
    assert client.get(f'/jobs/{job_id}').json() == saved


@pytest.mark.parametrize('mode', ['bullet', 'table', 'concept'])
@pytest.mark.parametrize('confidence', [.72, .87])
def test_analyzer_payload_evidence_and_label_metadata_persist(client, session_factory, tmp_path, mode, confidence):
    job_id = upload(client, tmp_path, mode)
    async def analyzer(document, requested_mode):
        assert document.page_count == 3 and document.extracted_text[1]['text'] == ''
        return analysis(document, requested_mode, confidence)
    processing.process_job(job_id, session_factory, analyzer=analyzer)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'completed'
    doc_id = saved['job_files'][0]['document_id']
    result = saved['result_data']['documents'][str(doc_id)]
    assert result['analysis_status'] == 'completed'
    assert result['label']['ai_confidence'] == confidence
    assert result['label']['confidence_level'] == ('low' if confidence < .8 else 'high')
    assert result['label']['review_state'] == 'needs_review'  # no automatic human confirmation
    verified = next(c for c in saved['citations'] if not c['unverified'])
    assert verified['document_id'] == doc_id and verified['page'] == 3
    assert verified['text_span'] == 'Late fee 0.05% per day.'
    assert verified['claim_text'] == '0.05% per day'
    if mode == 'bullet':
        assert result['output']['actions'] == [] and result['output']['limitation']
        assert 'insufficient_actions' in result['warnings']
        assert not any(c['unverified'] for c in saved['citations'])
    if mode == 'table':
        for field in ('value', 'payment_term'):
            assert result['output'][field]['text'] is None
            assert result['output'][field]['evidence'] == [] and result['output'][field]['unverified'] is True
    reader = client.get(result['reader']['url'])
    displayed = tmp_path / 'displayed.pdf'
    displayed.write_bytes(reader.content)
    assert extract_pdf(displayed)['extracted_text'][verified['page'] - 1]['text'] == verified['text_span']
    with session_factory() as db:
        document = db.get(Document, doc_id)
        assert document.ai_label == 'Contract' and document.ai_confidence == confidence
        assert document.folder_id is None and document.user_label is None
    assert client.get(f'/jobs/{job_id}').json() == saved


@pytest.mark.parametrize('confidence, expected_level, expected_state', [
    (0.87, 'high', 'needs_review'),
    (0.80, 'high', 'needs_review'),
    (0.79, 'low', 'needs_review'),
    (0.72, 'low', 'needs_review'),
])
def test_label_prediction_confidence_boundary_and_no_folder_auto_assignment(
    client, session_factory, tmp_path, confidence, expected_level, expected_state
):
    """Test 87%, 72% and the 79%/80% boundary using controlled classifier outputs.
    - Run label prediction on extracted document text.
    - Reuse ai_label and ai_confidence independently of folder_id and user_label.
    - Scores below 80% require review ('low'); scores at or above 80% are high-confidence AI suggestions ('high').
    - Scores at or above 80% are NOT user-confirmed labels (review_state stays 'needs_review').
    - Never auto-assign folders (folder_id is None).
    """
    job_id = upload(client, tmp_path, 'bullet')

    async def controlled_classifier(document, mode):
        # Verify classifier receives extracted document text
        assert document.extracted_text and any(p['text'] for p in document.extracted_text)
        return analysis(document, mode, confidence=confidence)

    processing.process_job(job_id, session_factory, analyzer=controlled_classifier)

    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'completed'
    doc_id = saved['job_files'][0]['document_id']
    doc_result = saved['result_data']['documents'][str(doc_id)]
    label = doc_result['label']

    # AI prediction attributes
    assert label['ai_label'] == 'Contract'
    assert label['ai_confidence'] == pytest.approx(confidence)
    assert label['confidence_level'] == expected_level
    # Scores at or above 80% are NOT user-confirmed labels; review_state stays needs_review
    assert label['review_state'] == expected_state
    # User label is not auto-assigned
    assert label['user_label'] is None

    # Verify database model persistence
    with session_factory() as db:
        document = db.get(Document, doc_id)
        assert document.ai_label == 'Contract'
        assert document.ai_confidence == pytest.approx(confidence)
        # Folder is never auto-assigned
        assert document.folder_id is None
        # User label is never auto-assigned
        assert document.user_label is None
        assert document.review_state == ReviewState.NEEDS_REVIEW


@pytest.mark.parametrize('confidence', [0.87, 0.72])
def test_ai_suggestion_keeps_human_label_review_and_folder(client, session_factory, tmp_path, confidence):
    job_id = upload(client, tmp_path)
    with session_factory() as db:
        document = db.get(Job, job_id).job_files[0].document
        folder = Folder(owner_id=123, name='My folder')
        db.add(folder)
        db.flush()
        document.folder_id = folder.id
        doc_id, folder_id = document.id, folder.id
        db.commit()
    updated = client.patch(f'/documents/{doc_id}/label', json={'user_label': 'My chosen label', 'review_state': 'confirmed'})
    assert updated.status_code == 200
    async def analyzer(document, mode):
        return analysis(document, mode, confidence=confidence)
    processing.process_job(job_id, session_factory, analyzer=analyzer)
    with session_factory() as db:
        document = db.get(Document, doc_id)
        assert document.folder_id == folder_id and document.user_label == 'My chosen label'
        assert document.review_state == ReviewState.CONFIRMED
        assert document.ai_label == 'Contract'
        assert document.ai_confidence == pytest.approx(confidence)
    label = client.get(f'/jobs/{job_id}').json()['result_data']['documents'][str(doc_id)]['label']
    assert label['user_label'] == 'My chosen label' and label['review_state'] == 'confirmed'
    assert label['confidence_level'] == ('high' if confidence >= 0.8 else 'low')


@pytest.mark.parametrize('bad_reference', ['document_id', 'page', 'quote', 'reader_version', 'start'])
def test_invalid_evidence_is_unverified_without_losing_extracted_result(client, session_factory, tmp_path, bad_reference):
    job_id = upload(client, tmp_path)
    def mutate(evidence):
        invalid = {'document_id': 99999, 'page': 2, 'quote': 'x' * len(evidence['quote']),
                   'reader_version': '0' * 64, 'start': 1}
        evidence[bad_reference] = invalid[bad_reference]
    async def analyzer(document, mode):
        return analysis(document, mode, mutation=mutate)
    processing.process_job(job_id, session_factory, analyzer=analyzer)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == saved['job_files'][0]['status'] == 'completed'
    assert saved['completed_count'] == 1
    doc_id = saved['job_files'][0]['document_id']
    claim = saved['result_data']['documents'][str(doc_id)]['output']['bullets'][0]
    assert claim['unverified'] and claim['evidence'] == []
    assert 'invalid_evidence' in claim['verification_issues']
    assert all(item['unverified'] and item['page'] is None and item['text_span'] is None for item in saved['citations'])
    with session_factory() as db:
        document = db.get(Job, job_id).job_files[0].document
        assert document.page_count == 3 and document.extracted_text and document.ai_label == 'Contract'
    assert client.get(f'/documents/{doc_id}/pages').status_code == 200


def test_broken_pdf_fails_only_its_file_and_good_file_still_completes(client, session_factory, tmp_path):
    source = make_pdf(tmp_path / 'good.pdf', [b'BT /F1 12 Tf 72 720 Td (Good file) Tj ET'])
    response = client.post('/upload', files=[
        ('files', ('broken.pdf', b'not really a PDF', 'application/pdf')),
        ('files', ('good.pdf', source.read_bytes(), 'application/pdf')),
    ])
    job_id = int(response.json()['jobId'])
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    broken, good = saved['job_files']
    assert saved['status'] == 'failed' and saved['completed_count'] == 1
    assert broken['status'] == 'failed' and broken['attempt_count'] == 1
    assert 'invalid_rendered_pdf' in broken['error_message']
    assert good['status'] == 'completed'
    assert set(saved['result_data']['documents']) == {str(good['document_id'])}
    assert client.get(f'/jobs/{job_id}').json() == saved


def test_extraction_timeouts_reuse_three_attempt_budget_and_do_not_stop_batch(client, session_factory, tmp_path, monkeypatch):
    job_id = upload(client, tmp_path, count=2)
    with session_factory() as db:
        first_id = db.get(Job, job_id).job_files[0].document_id
    original = processing.prepare_document
    calls, transitions = [], []
    async def prepare(document, **kwargs):
        calls.append(document.id)
        if document.id == first_id:
            raise TimeoutError
        return await original(document, **kwargs)
    def observe(db, _):
        transitions.extend((item.status, item.attempt_count) for item in db.dirty if isinstance(item, JobFile))
    monkeypatch.setattr(processing, 'prepare_document', prepare)
    event.listen(session_factory.class_, 'after_flush', observe)
    try:
        processing.process_job(job_id, session_factory)
    finally:
        event.remove(session_factory.class_, 'after_flush', observe)
    assert calls[:3] == [first_id] * 3 and len(calls) == 4
    assert all((JobStatus.TIMED_OUT, attempt) in transitions for attempt in (1, 2, 3))
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'failed' and saved['completed_count'] == 1
    first, second = saved['job_files']
    assert first['status'] == 'failed' and first['attempt_count'] == 3
    assert second['status'] == 'completed'
    assert str(first_id) not in saved['result_data']['documents']


def test_analyzer_timeout_retries_after_real_extraction_then_saves_once(client, session_factory, tmp_path):
    job_id = upload(client, tmp_path)
    calls = 0
    async def analyzer(document, mode):
        nonlocal calls
        calls += 1
        assert document.page_count == 3
        if calls < 3:
            raise TimeoutError
        return analysis(document, mode)
    processing.process_job(job_id, session_factory, analyzer=analyzer)
    saved = client.get(f'/jobs/{job_id}').json()
    file = saved['job_files'][0]
    assert calls == file['attempt_count'] == 3
    assert file['timeout_seconds'] == 39 and file['error_message'] is None
    assert saved['status'] == file['status'] == 'completed' and saved['completed_count'] == 1
    assert len(saved['citations']) == 1  # unsupported actions and failed attempts leave no citations
    assert len(saved['result_data']['documents']) == 1


def test_failed_result_commit_rolls_back_metadata_artifact_and_continues(client, session_factory, tmp_path, monkeypatch):
    job_id = upload(client, tmp_path, count=2)
    original = session_factory.class_.commit
    failed = False
    def fail_first_result(db):
        nonlocal failed
        if not failed and any(isinstance(item, Job) and item.result_data for item in db.dirty):
            failed = True
            raise SQLAlchemyError('private database error')
        return original(db)
    monkeypatch.setattr(session_factory.class_, 'commit', fail_first_result)
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert failed and saved['completed_count'] == 1 and saved['status'] == 'failed'
    first, second = saved['job_files']
    assert first['status'] == 'failed' and second['status'] == 'completed'
    assert 'private' not in first['error_message']
    with session_factory() as db:
        document = db.get(Document, first['document_id'])
        assert document.page_count is None and document.extracted_text is None
        assert not list((Path(document.storage_path).parent / '.reader' / str(document.id)).rglob('*.pdf'))


def test_textless_pdf_is_extracted_without_fabricated_content(client, session_factory, tmp_path):
    source = make_pdf(tmp_path / 'blank.pdf', [b'', b''])
    response = client.post('/upload', files=[('files', ('blank.pdf', source.read_bytes(), 'application/pdf'))])
    job_id = int(response.json()['jobId'])
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'completed'
    doc_id = saved['job_files'][0]['document_id']
    result = saved['result_data']['documents'][str(doc_id)]
    assert result['output']['bullets'] == [] and result['output']['actions'] == []
    assert 'no_text_layer' in result['warnings'] and saved['citations'] == []
    assert client.get(f'/documents/{doc_id}/pages').json()['pages'][1]['text'] == ''


@pytest.mark.parametrize('fmt', [FileFormat.DOCX, FileFormat.PPTX])
def test_office_upload_pipeline_uses_actual_rendered_reader_pages(client, session_factory, sources, fmt):
    from app.services.reader_extraction import find_soffice, ReaderConversionError
    try:
        find_soffice()
    except ReaderConversionError:
        pytest.skip('LibreOffice is required for the real conversion integration test')
    source = sources[fmt]
    response = client.post('/upload', files=[('files', (source.name, source.read_bytes(), 'application/octet-stream'))])
    job_id = int(response.json()['jobId'])
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'completed'
    doc_id = saved['job_files'][0]['document_id']
    result = saved['result_data']['documents'][str(doc_id)]
    pages = client.get(f'/documents/{doc_id}/pages').json()
    assert result['reader']['page_count'] == pages['page_count'] == (2 if fmt == FileFormat.DOCX else 3)
    assert result['reader']['page_kind'] == ('page' if fmt == FileFormat.DOCX else 'slide')
    assert saved['job_files'][0]['timeout_seconds'] == 30 + 3 * pages['page_count']
    assert all(page['reader']['sha256'] == result['reader']['version'] for page in pages['pages'])


def test_missing_converter_is_an_explicit_file_failure(client, session_factory, sources, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'SOFFICE_BINARY', str(tmp_path / 'missing-soffice.exe'))
    source = sources[FileFormat.DOCX]
    response = client.post('/upload', files=[('files', (source.name, source.read_bytes(), 'application/octet-stream'))])
    job_id = int(response.json()['jobId'])
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'failed' and saved['completed_count'] == 0
    assert 'converter_unavailable' in saved['job_files'][0]['error_message']
    assert saved['job_files'][0]['attempt_count'] == 1 and saved['result_data'] is None


def test_results_and_reader_survive_database_engine_restart(client, session_factory, tmp_path):
    job_id = upload(client, tmp_path)
    # Move the committed upload to a disk-backed DB, then actually dispose and
    # recreate the engine rather than relying on the original ORM identity map.
    database_url = 'sqlite:///' + str(tmp_path / 'restart.sqlite')
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with session_factory() as old, factory() as new:
        old_job = old.get(Job, job_id)
        new.add(User(id=123, username='restart', email='restart@example.com', password_hash='unused'))
        document = old_job.job_files[0].document
        new.add(Document(id=document.id, owner_id=123, original_filename=document.original_filename,
                         storage_path=document.storage_path, file_format=document.file_format,
                         file_size_bytes=document.file_size_bytes, expires_at=document.expires_at))
        new.add(Job(id=job_id, owner_id=123, mode=old_job.mode, file_count=1))
        new.flush()
        new.add(JobFile(job_id=job_id, document_id=document.id))
        new.commit()
    async def analyzer(document, mode):
        return analysis(document, mode)
    processing.process_job(job_id, factory, analyzer=analyzer)
    with factory() as db:
        job = db.get(Job, job_id)
        assert job.status == JobStatus.COMPLETED
        saved = json.loads(json.dumps(job.result_data))
        doc_id = job.job_files[0].document_id
        saved_pages = job.job_files[0].document.extracted_text
        assert len(job.citations) == 1
    engine.dispose()
    restarted = create_engine(database_url)
    factory = sessionmaker(bind=restarted)
    try:
        processing.process_job(job_id, factory, analyzer=AsyncMock(side_effect=AssertionError('must not rerun')))
        with factory() as db:
            job = db.get(Job, job_id)
            assert job.result_data == saved and job.status == JobStatus.COMPLETED
            assert db.get(Document, doc_id).extracted_text == saved_pages
            assert len(job.citations) == 1
            from app.services.reader_extraction import reader_representation
            path, _ = reader_representation(db.get(Document, doc_id))
            assert extract_pdf(path)['extracted_text'][2]['text'] == 'Late fee 0.05% per day.'
    finally:
        restarted.dispose()


def test_cancelling_extraction_kills_worker_before_removing_work_directory(tmp_path, monkeypatch):
    source = make_pdf(tmp_path / 'cancel.pdf', [b''])
    document = processing.DocumentInput(1, str(source), None, FileFormat.PDF)
    real_spawn = asyncio.create_subprocess_exec
    spawned, work_paths = [], []
    async def hanging_worker(*args, **kwargs):
        work_paths.append(Path(args[-1]))
        process = await real_spawn(sys.executable, '-c', 'import time; time.sleep(60)', **kwargs)
        spawned.append(process)
        return process
    # stop_worker also spawns taskkill on Windows, so let that command pass.
    async def spawn(*args, **kwargs):
        if args[0] == 'taskkill':
            return await real_spawn(*args, **kwargs)
        return await hanging_worker(*args, **kwargs)
    monkeypatch.setattr(job_extraction.asyncio, 'create_subprocess_exec', spawn)
    async def cancel():
        task = asyncio.create_task(job_extraction.prepare_document(document))
        while not spawned:
            await asyncio.sleep(.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(cancel())
    assert spawned[0].returncode is not None
    assert work_paths and all(not path.exists() for path in work_paths)


def test_reported_page_count_tightens_extraction_deadline_before_text_finishes(tmp_path, monkeypatch):
    source = make_pdf(tmp_path / 'slow-text.pdf', [b''])
    document = processing.DocumentInput(1, str(source), None, FileFormat.PDF)
    real_spawn = asyncio.create_subprocess_exec
    workers, paths, reported = [], [], []
    async def spawn(*args, **kwargs):
        if args[0] == 'taskkill':
            return await real_spawn(*args, **kwargs)
        work = Path(args[-1])
        paths.append(work)
        script = ('import pathlib,sys,time; '
                  'pathlib.Path(sys.argv[1], "page_count.json").write_text(\'{"page_count": 5}\'); '
                  'time.sleep(60)')
        worker = await real_spawn(sys.executable, '-c', script, str(work), **kwargs)
        workers.append(worker)
        return worker
    def on_pages(count):
        reported.append(count)
        return .1  # short real deadline instead of waiting 45 seconds in this test
    monkeypatch.setattr(job_extraction.asyncio, 'create_subprocess_exec', spawn)
    async def extract():
        with pytest.raises(TimeoutError):
            await job_extraction.prepare_document(document, on_page_count=on_pages)
    asyncio.run(extract())
    assert reported == [5] and workers[0].returncode is not None
    assert all(not path.exists() for path in paths)
