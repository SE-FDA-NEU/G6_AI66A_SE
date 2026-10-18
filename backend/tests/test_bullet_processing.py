"""Bullet/action grounding, persisted limits and the US03/US07 deadline."""
import asyncio
from datetime import timedelta
import json
import time

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
             'Compare 2 supplier quotations before renewal.']
    lines += [f'Report section {index}.' for index in range(4, 16)]
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
        return {'label': 'Report', 'confidence': 87, 'bullets': [{'t': lines[0], 's': [source[lines[0]]]}],
                'actions': actions}, {'promptTokenCount': 100, 'candidatesTokenCount': 60}

    monkeypatch.setattr(gemini, 'generate', generate)
    return int(response.json()['jobId']), state


@pytest.mark.parametrize('case, supported', [('two', 2), ('zero', 0), ('one', 1), ('duplicate', 1),
                                          ('no-source', 1), ('unknown-source', 1), ('wrong-number', 1)])
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


@pytest.mark.parametrize('words, completed', [(1000, True), (1001, False)])
def test_inclusive_word_limit_is_enforced_before_persistence(client, session_factory, bullet_job, words, completed):
    job_id, _ = bullet_job

    async def analyzer(document, mode):
        page = document.extracted_text[0]
        evidence = {'document_id': document.id, 'page': 1, 'start': 0, 'end': len(page['text']),
                    'quote': page['text'], 'reader_version': page['reader']['sha256']}
        text = ' '.join(['report'] * (words - len(INSUFFICIENT_ACTIONS.split())))
        return {'output': {'type': 'bullet', 'bullets': [{'text': text, 'evidence': [evidence], 'unverified': False}],
                           'actions': [], 'limitation': INSUFFICIENT_ACTIONS}}

    processing.process_job(job_id, session_factory, analyzer=analyzer)
    saved = client.get(f'/jobs/{job_id}').json()
    assert (saved['status'] == 'completed') == completed
    if completed:
        output = next(iter(saved['result_data']['documents'].values()))['output']
        assert len(output['bullets'][0]['text'].split()) + len(output['limitation'].split()) == 1000
    else:
        assert saved['result_data']['documents'] == {} and saved['citations'] == []
        assert 'invalid_result' in saved['job_files'][0]['error_message']


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
