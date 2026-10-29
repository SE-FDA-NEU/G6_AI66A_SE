"""Financial comparison uses the existing extraction, evidence and persistence pipeline."""
import asyncio
from datetime import timedelta
import json
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.models import Job
from app.services import gemini_analysis as gemini, processing
from test_pdf_extraction import make_pdf
from test_acceptance_fixtures import install_controlled_provider, manifest, upload


AMOUNTS = ['1,200,000,000 VND', '2,500,000,000 VND', '999,999.99 USD', '0.00 VND', '750,000,000 VND']


@pytest.fixture
def contract_batch(client, monkeypatch):
    by_key = {spec['key']: spec for spec in manifest()['documents']}
    specs = [by_key[f'contract-{number}'] for number in range(1, 6)]
    calls = install_controlled_provider(monkeypatch, specs, 'table')
    return upload(client, specs, 'table'), specs, calls


def test_committed_contracts_preserve_five_rows_and_physical_sources(
        client, session_factory, contract_batch):
    """TC-US01-01: normal batch, exact amounts/units and persisted source offsets."""
    job_id, specs, calls = contract_batch
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'completed'
    assert saved['completed_count'] == saved['file_count'] == len(calls) == 5
    rows = saved['result_data']['documents']
    assert len(rows) == 5
    with session_factory() as db:
        job = db.get(Job, job_id)
        assert job.result_data == saved['result_data']
        for spec, file in zip(specs, saved['job_files']):
            row = rows[str(file['document_id'])]
            document = next(link.document for link in job.job_files
                            if link.document_id == file['document_id'])
            assert file['status'] == 'completed'
            assert row['original_filename'] == spec['filename']
            assert row['output']['value']['text'] == spec['fields']['value']
            assert row['output']['penalty']['text'] == '0.05% per day'
            for field, expected in spec['fields'].items():
                claim = row['output'][field]
                assert claim['text'] == expected
                assert claim['unverified'] is (expected is None)
                if expected is None:
                    assert claim['evidence'] == []
                    continue
                assert len(claim['evidence']) == 1
                evidence = claim['evidence'][0]
                answer = spec['field_evidence'][field]
                assert evidence['document_id'] == document.id
                assert evidence['page'] == answer['page']
                page = document.extracted_text[evidence['page'] - 1]
                assert page['text'][evidence['start']:evidence['end']] == evidence['quote']
                assert expected in evidence['quote']
                assert evidence['start'] <= answer['start'] < answer['end'] <= evidence['end']
                assert evidence['reader_version'] == row['reader']['version']
    assert len(saved['citations']) == 14
    assert all(not citation['unverified'] for citation in saved['citations'])
    processing.process_job(job_id, session_factory)
    assert client.get(f'/jobs/{job_id}').json() == saved and len(calls) == 5


@pytest.mark.parametrize('elapsed, completed', [
    pytest.param(299.999, True, id='TC-US01-04-before-300s'),
    pytest.param(300.0, False, id='TC-US01-05-at-300s'),
    pytest.param(300.001, False, id='TC-US01-06-after-300s'),
])
@pytest.mark.parametrize('retry', [False, True], ids=['no-retry', 'one-timeout-retry'])
def test_contract_batch_deadline_rejects_late_fifth_row(
        client, session_factory, contract_batch, monkeypatch, elapsed, completed, retry):
    """Queue time plus all five contracts share one deadline, independent of file budgets."""
    job_id, _, calls = contract_batch
    now = processing.utcnow()
    with session_factory() as db:
        db.get(Job, job_id).created_at = now - timedelta(seconds=260)
        db.commit()
    monkeypatch.setattr(processing, 'utcnow', lambda: now)
    generate = gemini.generate
    clock = [0.0]
    retried = False
    budgets = []

    async def timed_generate(body):
        nonlocal retried
        if retry and not retried:
            retried = True
            clock[0] += 1
            raise TimeoutError
        clock[0] += 8 if len(calls) < 4 else elapsed - 292 - int(retry)
        return await generate(body)

    monkeypatch.setattr(gemini, 'generate', timed_generate)

    async def wait_for(coroutine, timeout):
        budgets.append(timeout)
        return await asyncio.wait_for(coroutine, timeout=timeout)

    # Only the worker sees fake time. Native extraction still uses the real event loop
    # for its subprocess polling, so a frozen clock cannot stall asyncio.sleep().
    monkeypatch.setattr(processing, 'asyncio', SimpleNamespace(
        get_running_loop=lambda: SimpleNamespace(time=lambda: clock[0]),
        wait_for=wait_for, run=asyncio.run))
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert len(calls) == 5
    assert saved['status'] == ('completed' if completed else 'failed')
    assert saved['completed_count'] == (5 if completed else 4)
    assert len(saved['result_data']['documents']) == (5 if completed else 4)
    assert all(file['status'] == 'completed' for file in saved['job_files'][:4])
    assert saved['job_files'][0]['attempt_count'] == (2 if retry else 1)
    assert budgets[-1] == pytest.approx(8 - int(retry))
    last = saved['job_files'][-1]
    assert last['attempt_count'] == 1
    assert last['status'] == ('completed' if completed else 'failed')
    assert len(saved['citations']) == (14 if completed else 12)
    if not completed:
        assert '300-second' in last['error_message']
        assert str(last['document_id']) not in saved['result_data']['documents']
    processing.process_job(job_id, session_factory)
    assert client.get(f'/jobs/{job_id}').json() == saved and len(calls) == 5


@pytest.mark.parametrize('queued_seconds', [300, 300.001])
def test_expired_contract_batch_never_calls_provider(
        client, session_factory, contract_batch, monkeypatch, queued_seconds):
    """TC-US01-07: queue time consumes the batch budget before extraction or AI."""
    job_id, _, calls = contract_batch
    now = processing.utcnow()
    with session_factory() as db:
        db.get(Job, job_id).created_at = now - timedelta(seconds=queued_seconds)
        db.commit()
    monkeypatch.setattr(processing, 'utcnow', lambda: now)
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'failed' and saved['completed_count'] == 0
    assert calls == [] and saved['result_data']['documents'] == {} and saved['citations'] == []
    for file in saved['job_files']:
        assert file['status'] == 'failed' and file['attempt_count'] == 1
        assert '300-second' in file['error_message']


@pytest.fixture
def financial_batch(client, session_factory, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', SecretStr('isolated-financial-test-key'))
    monkeypatch.setattr(settings, 'GEMINI_CACHE_ENABLED', False)
    files = []
    for index, amount in enumerate(AMOUNTS):
        lines = [f'Contract value: {amount}',
                 'Payment term: Within 30 days' if index < 4 else 'No payment schedule provided.',
                 'Penalty: 0.05% per day']
        source = make_pdf(tmp_path / f'contract-{index + 1}.pdf', [
            f'BT /F1 12 Tf 72 720 Td ({line}) Tj ET'.encode() for line in lines
        ])
        files.append(('files', (source.name, source.read_bytes(), 'application/pdf')))
    uploaded = client.post('/upload', data={'mode': 'table'}, files=files)
    assert uploaded.status_code == 202
    job_id = int(uploaded.json()['jobId'])
    state = {'calls': 0, 'overrides': {}, 'error': None}

    async def generate(body):
        state['calls'] += 1
        excerpts = json.loads(body['contents'][0]['parts'][0]['text'])
        if state['error'] and any(AMOUNTS[-1] in text for _, text in excerpts):
            raise state['error']
        result = {'label': 'Hợp đồng', 'confidence': 90}
        for field, prefix in [('value', 'Contract value: '), ('payment_term', 'Payment term: '), ('penalty', 'Penalty: ')]:
            result[field] = {'t': None, 's': None}
            for source_id, text in excerpts:
                if text.startswith(prefix):
                    result[field] = {'t': state['overrides'].get(field, text.removeprefix(prefix)), 's': [source_id]}
                    break
        return result, {}

    # Mock only the paid provider; extraction, verification, labels, rows and DB writes are real.
    monkeypatch.setattr(gemini, 'generate', generate)
    return job_id, state


def test_five_financial_rows_and_labels_persist_exact_numbers_units_and_field_evidence(client, session_factory, financial_batch):
    job_id, state = financial_batch
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'completed' and saved['completed_count'] == saved['file_count'] == 5
    assert len(saved['result_data']['documents']) == 5 and state['calls'] == 5
    for index, file in enumerate(saved['job_files']):
        document_id = file['document_id']
        row = saved['result_data']['documents'][str(document_id)]
        assert row['original_filename'] == f'contract-{index + 1}.pdf'
        assert row['output']['value']['text'] == AMOUNTS[index]
        assert row['output']['penalty']['text'] == '0.05% per day'
        assert row['label']['ai_label'] == 'Hợp đồng' and row['label']['ai_confidence'] == .9
        assert file['status'] == 'completed' and file['timeout_seconds'] <= 300
        if index == 4:
            missing = row['output']['payment_term']
            assert missing['text'] is None and missing['unverified'] and missing['evidence'] == []
        else:
            assert row['output']['payment_term']['text'] == 'Within 30 days'
        with session_factory() as db:
            stored_job = db.get(Job, job_id)
            stored_document = next(link.document for link in stored_job.job_files if link.document_id == document_id)
            assert stored_document.ai_label == 'Hợp đồng' and stored_document.ai_confidence == .9
            for field in ('value', 'payment_term', 'penalty'):
                claim = row['output'][field]
                if claim['text'] is None:
                    continue
                assert not claim['unverified'] and len(claim['evidence']) == 1
                evidence = claim['evidence'][0]
                assert evidence['document_id'] == document_id and claim['text'] in evidence['quote']
                page = stored_document.extracted_text[evidence['page'] - 1]
                assert page['text'][evidence['start']:evidence['end']] == evidence['quote']
            assert stored_job.result_data == saved['result_data']
    assert len(saved['citations']) == 14
    # Reopening or reprocessing a terminal job reads its persisted rows without another AI call.
    processing.process_job(job_id, session_factory)
    assert client.get(f'/jobs/{job_id}').json() == saved and state['calls'] == 5


@pytest.mark.parametrize('field, unsupported', [
    ('value', '1,200,000,001 VND'),
    ('value', '1,200,000,000 USD'),
    ('value', '1.2 billion VND'),
    ('penalty', '0.5% per day'),
    ('penalty', '0.05% per month'),
    ('payment_term', 'Within 60 days'),
])
def test_changed_numbers_currency_or_period_are_saved_as_unverified(client, session_factory, financial_batch, field, unsupported):
    job_id, state = financial_batch
    state['overrides'][field] = unsupported
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    first_id = saved['job_files'][0]['document_id']
    claim = saved['result_data']['documents'][str(first_id)]['output'][field]
    assert claim['text'] == unsupported and claim['unverified']
    assert 'unsupported_fact' in claim['verification_issues']
    assert claim['evidence']  # Keep the valid source available for human review.
    assert client.get(f'/jobs/{job_id}').json()['result_data']['documents'][str(first_id)]['output'][field] == claim


@pytest.mark.parametrize('error, attempts', [
    (TimeoutError(), 3),
    (gemini.GeminiAnalysisError('gemini_unavailable', 'Provider unavailable.'), 1),
])
def test_financial_batch_preserves_finished_rows_when_one_contract_times_out_or_fails(client, session_factory, financial_batch, error, attempts):
    job_id, state = financial_batch
    state['error'] = error
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'failed' and saved['completed_count'] == 4
    assert len(saved['result_data']['documents']) == 4
    last = saved['job_files'][-1]
    assert last['status'] == 'failed' and last['attempt_count'] == attempts
    assert last['error_message'] and last['timeout_seconds'] <= 300
    assert str(last['document_id']) not in saved['result_data']['documents']
    assert saved['finished_at'] is not None
