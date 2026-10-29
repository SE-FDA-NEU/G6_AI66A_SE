"""Bullet/action grounding, persisted limits and the US03/US07 deadline."""
import asyncio
from datetime import timedelta
import json
import time
from types import SimpleNamespace

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import settings
from app.models import Job, JobMode
from app.schemas.result import BulletOutput
from app.services import gemini_analysis as gemini, processing
from app.services.bullet_output import INSUFFICIENT_ACTIONS
from test_pdf_extraction import make_pdf


@pytest.fixture
def bullet_job(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', SecretStr('test-only-no-live-call'))
    monkeypatch.setattr(settings, 'GEMINI_CACHE_ENABLED', False)
    lines = ['Payment is due within 30 days.', 'Review the budget within 30 days.',
             'Compare 2 supplier quotations before renewal.', 'Archive the signed delivery receipt.']
    lines += [f'Report section {index}.' for index in range(5, 16)]
    pdf = make_pdf(tmp_path / 'report.pdf', [
        f'BT /F1 12 Tf 72 720 Td ({line}) Tj ET'.encode() for line in lines
    ])
    response = client.post('/upload', data={'mode': 'bullet'},
                           files=[('files', ('report.pdf', pdf.read_bytes(), 'application/pdf'))])
    assert response.status_code == 202
    state = {'calls': 0, 'case': 'two'}

    async def generate(body):
        state['calls'] += 1
        wire = json.loads(body['contents'][0]['parts'][0]['text'])
        source = {text: source_id for source_id, text in wire}
        actions = [{'t': text, 's': [source[text]]} for text in lines[1:3]]
        case = state['case']
        if case in ('zero', 'one'):
            actions = actions[:0 if case == 'zero' else 1]
        elif case == 'duplicate':
            actions[1] = dict(actions[0])
        elif case == 'no-source':
            actions[1]['s'] = None
        elif case == 'unknown-source':
            actions[1]['s'] = [999]
        elif case == 'wrong-number':
            actions[1]['t'] = 'Compare 3 supplier quotations before renewal.'
        elif case == 'three':
            actions.append({'t': lines[3], 's': [source[lines[3]]]})
        result = {'label': 'Report', 'confidence': 87, 'bullets': [{'t': lines[0], 's': [source[lines[0]]]}],
                  'actions': actions}
        result.update(state.get('override', {}))
        return result, {'promptTokenCount': 100, 'candidatesTokenCount': 60}

    monkeypatch.setattr(gemini, 'generate', generate)
    return int(response.json()['jobId']), state


@pytest.mark.parametrize('case, supported', [
    pytest.param('two', 2, id='TC-US03-01-two-supported-actions'),
    pytest.param('one', 1, id='TC-US03-02-one-supported-action'),
    ('zero', 0), ('duplicate', 1), ('no-source', 1), ('unknown-source', 1), ('wrong-number', 1),
])
def test_structured_bullets_and_only_grounded_distinct_actions_persist(client, session_factory, bullet_job, case, supported):
    job_id, state = bullet_job
    state['case'] = case
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'completed' and saved['completed_count'] == 1
    file = saved['job_files'][0]
    row = saved['result_data']['documents'][str(file['document_id'])]
    assert row['reader']['page_count'] == 15 and file['timeout_seconds'] == 75
    assert row['mode'] == row['output']['type'] == 'bullet'
    output = row['output']
    assert output['bullets'][0]['text'] == 'Payment is due within 30 days.'
    assert len(output['actions']) == supported
    assert (output['limitation'] == INSUFFICIENT_ACTIONS) == (supported < 2)
    assert ('insufficient_actions' in row['warnings']) == (supported < 2)
    with session_factory() as db:
        job = db.get(Job, job_id)
        assert job.result_data == saved['result_data']
        document = job.job_files[0].document
        for claim in output['bullets'] + output['actions']:
            assert not claim['unverified'] and claim['evidence']
            for evidence in claim['evidence']:
                assert evidence['document_id'] == document.id
                page = document.extracted_text[evidence['page'] - 1]
                assert page['text'][evidence['start']:evidence['end']] == evidence['quote']
    assert len(saved['citations']) == 1 + supported
    processing.process_job(job_id, session_factory)
    assert client.get(f'/jobs/{job_id}').json() == saved and state['calls'] == 1


@pytest.mark.parametrize('words, completed', [
    pytest.param(999, True, id='TC-US03-04-999-words'),
    pytest.param(1000, True, id='TC-US03-05-1000-words'),
    pytest.param(1001, False, id='TC-US03-06-1001-words'),
])
@pytest.mark.parametrize('action_count', [1, 2])
def test_inclusive_word_limit_is_enforced_before_persistence(
        client, session_factory, bullet_job, words, completed, action_count):
    """Count bullets, actions and the explicit fallback limitation in the public word budget."""
    job_id, _ = bullet_job

    async def analyzer(document, mode):
        def claim(text, number):
            page = document.extracted_text[number - 1]
            evidence = {'document_id': document.id, 'page': number, 'start': 0, 'end': len(page['text']),
                        'quote': page['text'], 'reader_version': page['reader']['sha256']}
            return {'text': text, 'evidence': [evidence], 'unverified': False}
        actions = [claim(document.extracted_text[number - 1]['text'], number)
                   for number in range(2, 2 + action_count)]
        limitation = INSUFFICIENT_ACTIONS if action_count == 1 else None
        action_words = sum(len(action['text'].split()) for action in actions)
        text = ' '.join(['report'] * (words - action_words - len((limitation or '').split())))
        return {'output': {'type': 'bullet', 'bullets': [claim(text, 1)],
                           'actions': actions, 'limitation': limitation}}

    processing.process_job(job_id, session_factory, analyzer=analyzer)
    saved = client.get(f'/jobs/{job_id}').json()
    assert (saved['status'] == 'completed') == completed
    if completed:
        output = next(iter(saved['result_data']['documents'].values()))['output']
        assert sum(len(claim['text'].split()) for claim in output['bullets'] + output['actions']) + len(
            (output['limitation'] or '').split()) == words
        assert len(output['actions']) == action_count
        assert output['limitation'] == (INSUFFICIENT_ACTIONS if action_count == 1 else None)
        assert len(saved['citations']) == 1 + action_count
    else:
        assert saved['result_data']['documents'] == {} and saved['citations'] == []
        assert 'invalid_result' in saved['job_files'][0]['error_message']
    processing.process_job(job_id, session_factory)
    assert client.get(f'/jobs/{job_id}').json() == saved


@pytest.mark.parametrize('case, override', [
    pytest.param('two', {'bullets': 'unstructured summary'}, id='TC-US03-03-unstructured-bullets'),
    pytest.param('two', {'actions': 'unstructured advice'}, id='unstructured-actions'),
    pytest.param('two', {'bullets': [{'t': True, 's': [0]}]}, id='invalid-bullet-text'),
    pytest.param('two', {'actions': [{'t': 'Advice', 's': ['page one']}]}, id='invalid-source-type'),
    pytest.param('two', {'actions': [{'t': 'Advice', 's': [-1]}]}, id='negative-source'),
    pytest.param('two', {'bullets': [{'t': 'Report', 's': [0], 'unverified': False}]}, id='forged-verification'),
    pytest.param('three', {}, id='TC-US03-07-three-actions-rejected'),
])
def test_invalid_ai_output_never_publishes_a_summary_or_recommendations(
        client, session_factory, bullet_job, case, override):
    job_id, state = bullet_job
    state.update(case=case, override=override)
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == saved['job_files'][0]['status'] == 'failed'
    assert saved['completed_count'] == 0 and saved['result_data']['documents'] == {} and saved['citations'] == []
    assert 'gemini_invalid_response' in saved['job_files'][0]['error_message']
    assert state['calls'] == 2  # One bounded repair attempt, without false success.
    with session_factory() as db:
        document = db.get(Job, job_id).job_files[0].document
        assert document.ai_label is None and document.extracted_text is None
    processing.process_job(job_id, session_factory)
    assert client.get(f'/jobs/{job_id}').json() == saved and state['calls'] == 2


@pytest.mark.parametrize('source_actions', [0, 1])
def test_source_with_fewer_than_two_actions_persists_an_explicit_limitation(
        client, session_factory, tmp_path, monkeypatch, source_actions):
    """TC-US03-08: the PDF itself lacks two actions; fabricated advice must not fill the gap."""
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', SecretStr('offline-insufficient-actions'))
    monkeypatch.setattr(settings, 'GEMINI_CACHE_ENABLED', False)
    summary = 'Quarterly report describes stable market demand.'
    action = 'Review the budget within 30 days.'
    lines = [summary, action if source_actions else 'Administrative contacts only.']
    lines += [f'Background section {number}.' for number in range(3, 16)]
    pdf = make_pdf(tmp_path / 'insufficient.pdf', [
        f'BT /F1 12 Tf 72 720 Td ({line}) Tj ET'.encode() for line in lines])
    uploaded = client.post('/upload', data={'mode': 'bullet'},
                           files=[('files', (pdf.name, pdf.read_bytes(), 'application/pdf'))])
    assert uploaded.status_code == 202
    job_id = int(uploaded.json()['jobId'])
    calls = []

    async def generate(body):
        calls.append(body)
        sources = {text: source_id for source_id, text in json.loads(body['contents'][0]['parts'][0]['text'])}
        actions = [{'t': action, 's': [sources[action]]}] if source_actions else []
        # A real source ID with an unsupported number must not verify invented advice.
        actions.append({'t': 'Compare 9 supplier quotations before renewal.', 's': [sources[summary]]})
        return {'label': None, 'confidence': None, 'bullets': [{'t': summary, 's': [sources[summary]]}],
                'actions': actions}, {}

    monkeypatch.setattr(gemini, 'generate', generate)
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'completed' and saved['completed_count'] == 1
    row = next(iter(saved['result_data']['documents'].values()))
    assert row['reader']['page_count'] == 15
    assert row['output']['bullets'][0]['text'] == summary
    assert [claim['text'] for claim in row['output']['actions']] == ([action] if source_actions else [])
    assert row['output']['limitation'] == INSUFFICIENT_ACTIONS
    assert row['warnings'].count('insufficient_actions') == 1
    assert len(saved['citations']) == 1 + source_actions
    assert all('9 supplier' not in citation['claim_text'] for citation in saved['citations'])
    with session_factory() as db:
        assert db.get(Job, job_id).result_data == saved['result_data']
    processing.process_job(job_id, session_factory)
    assert client.get(f'/jobs/{job_id}').json() == saved and len(calls) == 1


@pytest.mark.parametrize('elapsed, completed', [
    pytest.param(179.999, True, id='TC-US03-09-before-180s'),
    pytest.param(180.0, False, id='TC-US03-10-at-180s'),
    pytest.param(180.001, False, id='TC-US03-11-after-180s'),
])
@pytest.mark.parametrize('retry', [False, True], ids=['no-retry', 'one-timeout-retry'])
@pytest.mark.parametrize('stage', ['analysis', 'persistence'])
def test_fifteen_page_pdf_deadline_uses_fake_time_and_rejects_late_publication(
        client, session_factory, bullet_job, monkeypatch, elapsed, completed, retry, stage):
    """Queue time, extraction and retry time share the 180-second target."""
    job_id, state = bullet_job
    now = processing.utcnow()
    with session_factory() as db:
        db.get(Job, job_id).created_at = now - timedelta(seconds=120)
        db.commit()
    monkeypatch.setattr(processing, 'utcnow', lambda: now)
    clock = [0.0]
    budgets, prepared_pages = [], []
    prepare, generate, save = processing.prepare_document, gemini.generate, processing.save_analysis
    retried = False

    async def prepare_document(*args, **kwargs):
        prepared = await prepare(*args, **kwargs)
        prepared_pages.append(prepared.data['page_count'])
        clock[0] += 5
        return prepared

    async def timed_generate(body):
        nonlocal retried
        if retry and not retried:
            retried = True
            clock[0] += 1
            raise TimeoutError
        result = await generate(body)
        if stage == 'analysis':
            clock[0] = elapsed - 120
        return result

    def timed_save(*args, **kwargs):
        result = save(*args, **kwargs)
        if stage == 'persistence':
            clock[0] = elapsed - 120
        return result

    async def wait_for(coroutine, timeout):
        budgets.append(timeout)
        return await asyncio.wait_for(coroutine, timeout=timeout)

    # Keep native extraction's polling clock real; only the worker reads fake time.
    monkeypatch.setattr(processing, 'asyncio', SimpleNamespace(
        get_running_loop=lambda: SimpleNamespace(time=lambda: clock[0]), wait_for=wait_for, run=asyncio.run))
    monkeypatch.setattr(processing, 'prepare_document', prepare_document)
    monkeypatch.setattr(gemini, 'generate', timed_generate)
    monkeypatch.setattr(processing, 'save_analysis', timed_save)
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert prepared_pages == [15] * (2 if retry else 1)
    assert budgets[0] == pytest.approx(60) and budgets[-1] == pytest.approx(49 if retry else 55)
    assert saved['status'] == saved['job_files'][0]['status'] == ('completed' if completed else 'failed')
    assert saved['completed_count'] == int(completed)
    file = saved['job_files'][0]
    assert file['timeout_seconds'] == 75 and file['attempt_count'] == (2 if retry else 1)
    assert state['calls'] == 1
    if completed:
        row = saved['result_data']['documents'][str(file['document_id'])]
        assert row['reader']['page_count'] == 15 and len(row['output']['actions']) == 2
        assert len(saved['citations']) == 3
    else:
        assert '180-second target' in file['error_message']
        assert saved['result_data']['documents'] == {} and saved['citations'] == []
        with session_factory() as db:
            document = db.get(Job, job_id).job_files[0].document
            assert document.extracted_text is None and document.ai_label is None
    processing.process_job(job_id, session_factory)
    assert client.get(f'/jobs/{job_id}').json() == saved and state['calls'] == 1


def test_wire_requires_structured_bullets_actions_and_source_ids():
    body = gemini.request_body('bullet', [[0, 'Source recommendation.']])
    assert '1000 words' in body['systemInstruction']['parts'][0]['text']
    for invalid in [
        {'bullets': 'prose', 'actions': []},
        {'bullets': [], 'actions': [{'t': 'Invented advice', 's': ['page one']}]},
        {'bullets': [], 'actions': [{'t': 'Advice', 's': [0]}] * 3},
    ]:
        with pytest.raises(ValidationError):
            gemini.WireBullet.model_validate({'label': None, 'confidence': None, **invalid})
    with pytest.raises(ValidationError):
        BulletOutput(bullets=[{'text': 'word ' * 1001}])


def test_textless_source_has_explicit_action_limitation_without_calling_model(bullet_job):
    _, state = bullet_job
    document = processing.DocumentInput(1, 'unused', 15, extracted_text=[{'page': 1, 'text': ''}])
    result = asyncio.run(gemini.analyze_document(document, JobMode.BULLET))
    assert result.output.actions == [] and result.output.limitation == INSUFFICIENT_ACTIONS
    assert 'no_text_layer' in result.warnings and state['calls'] == 0


def test_180_second_target_is_shared_across_retries_and_cancels_inflight_work(client, session_factory, bullet_job, monkeypatch):
    job_id, _ = bullet_job
    with session_factory() as db:
        job = db.get(Job, job_id)
        job.created_at = processing.utcnow() + timedelta(seconds=1)
        job.job_files[0].document.page_count = 15
        db.commit()
    # Scale real timers down; the production target remains 180 seconds.
    assert processing.BULLET_TARGET_SECONDS == 180
    monkeypatch.setattr(processing, 'BULLET_TARGET_SECONDS', .12)
    original_wait_for = asyncio.wait_for
    budgets = []

    async def scaled_wait_for(coroutine, timeout):
        budgets.append(timeout)
        return await original_wait_for(coroutine, timeout=min(.05, timeout))

    monkeypatch.setattr(processing.asyncio, 'wait_for', scaled_wait_for)
    cancelled = []

    async def hanging(document, mode):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(document.id)

    processing.process_job(job_id, session_factory, hanging)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'failed' and saved['completed_count'] == 0
    assert 1 <= len(cancelled) <= 3
    # Subtracting monotonic clock values can round the upper bound by a few ns.
    assert budgets[-1] < budgets[0] <= .12 + 1e-8
    assert saved['job_files'][0]['error_message']
    assert saved['result_data']['documents'] == {} and saved['citations'] == []


def test_expired_queue_target_does_not_start_a_model_call(client, session_factory, bullet_job):
    job_id, state = bullet_job
    with session_factory() as db:
        db.get(Job, job_id).created_at = processing.utcnow() - timedelta(seconds=181)
        db.commit()
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'failed' and saved['completed_count'] == 0 and state['calls'] == 0
    assert '180-second target' in saved['job_files'][0]['error_message']


def test_late_result_is_not_committed_as_success(client, session_factory, bullet_job, monkeypatch):
    job_id, _ = bullet_job
    with session_factory() as db:
        job = db.get(Job, job_id)
        job.created_at = processing.utcnow() + timedelta(seconds=1)
        db.commit()
    monkeypatch.setattr(processing, 'BULLET_TARGET_SECONDS', .02)

    async def late(document, mode):
        time.sleep(.04)  # Deliberately uncancellable adapter; post-await guard must reject it.
        return {'summary': 'late result'}

    processing.process_job(job_id, session_factory, late)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'failed' and saved['result_data']['documents'] == {}
