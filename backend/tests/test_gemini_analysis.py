"""Gemini protocol, budgets, grounding and persistence without live API calls."""
import asyncio
from dataclasses import replace
import json

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.models import FileFormat, Job, JobMode
from app.services import gemini_analysis as gemini, processing
from app.services.pdf_extraction import extract_pdf
from test_pdf_extraction import make_pdf


@pytest.fixture
def document(tmp_path):
    pdf = make_pdf(tmp_path / 'source.pdf', [b'', b'BT /F1 12 Tf 72 720 Td (Late fee 0.05% per day.) Tj ET'])
    data = extract_pdf(pdf)
    for page in data['extracted_text']:
        page['reader'] = {'sha256': 'a' * 64, 'source_sha256': 'b' * 64, 'page_kind': 'page'}
    return processing.DocumentInput(17, str(pdf), 2, FileFormat.PDF, data['extracted_text'], 123)


@pytest.fixture
def api(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', SecretStr('test-only-secret-never-live'))
    monkeypatch.setattr(settings, 'GEMINI_MODEL', 'gemini-3.5-flash-lite')
    monkeypatch.setattr(settings, 'STORAGE_DIR', tmp_path / 'storage')
    calls = []
    state = {'status': 200, 'response': None, 'exception': None}
    async def handler(request):
        calls.append(request)
        if state.get('handler'):
            return await state['handler'](request)
        if state['exception']:
            raise state['exception']
        return httpx.Response(state['status'], json=state['response'])
    real_client = httpx.AsyncClient
    monkeypatch.setattr(gemini.httpx, 'AsyncClient', lambda **kwargs:
                        real_client(transport=httpx.MockTransport(handler), **kwargs))
    return state, calls


def response(mode='bullet', source=0):
    claim = {'t': 'Phạt chậm thanh toán 0.05% mỗi ngày.', 's': source}
    result = {'label': 'Hợp đồng', 'confidence': 87}
    if mode == 'bullet':
        result.update(bullets=[claim], actions=[{'t': 'Kiểm tra trước khi ký.', 's': None}])
    elif mode == 'table':
        result.update(value={'t': None, 's': None}, payment_term={'t': None, 's': None}, penalty=claim)
    else:
        result.update(concepts=[{'n': 'Phạt chậm trả', **claim}])
    return {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(result)}]}}],
            'usageMetadata': {'promptTokenCount': 200, 'candidatesTokenCount': 80, 'totalTokenCount': 280}}


@pytest.mark.parametrize('mode', list(JobMode))
def test_one_compact_request_maps_real_source_offsets_and_metadata(document, api, mode):
    state, calls = api
    state['response'] = response(mode.value)
    result = asyncio.run(processing.process_document(document, mode))
    assert len(calls) == 1 and result.analysis_status == 'completed'
    request = calls[0]
    assert request.url.host == 'generativelanguage.googleapis.com'
    assert not request.url.params and request.headers['x-goog-api-key'] == 'test-only-secret-never-live'
    body = json.loads(request.content)
    config = body['generationConfig']
    assert config['maxOutputTokens'] == settings.GEMINI_MAX_OUTPUT_TOKENS and config['candidateCount'] == 1
    assert config['thinkingConfig'] == {'thinkingLevel': 'minimal'}
    assert config['responseFormat']['text']['mimeType'] == 'APPLICATION_JSON'
    prompt = body['contents'][0]['parts'][0]['text']
    assert json.loads(prompt) == [[0, 'Late fee 0.05% per day.']]
    for unnecessary in ('positions', 'bbox', 'sha256', 'storage_path', 'document_id'):
        assert unnecessary not in prompt
    claim = (result.output.bullets[0] if mode == JobMode.BULLET else result.output.penalty
             if mode == JobMode.TABLE else result.output.concepts[0].description)
    evidence = claim.evidence[0]
    assert not claim.unverified and evidence.page == 2
    assert document.extracted_text[1]['text'][evidence.start:evidence.end] == evidence.quote
    assert evidence.document_id == document.id and evidence.reader_version == 'a' * 64
    assert result.label.ai_confidence == .87
    assert result.analysis_metadata.input_tokens == 200 and result.analysis_metadata.output_tokens == 80
    if mode == JobMode.BULLET:
        assert result.output.actions == [] and result.output.limitation
        assert 'insufficient_actions' in result.warnings


def test_cache_reuses_wire_response_after_reupload_but_remaps_citations(document, api):
    state, calls = api
    state['response'] = response()
    first = asyncio.run(gemini.analyze_document(document, JobMode.BULLET))
    second_document = replace(document, id=99, extracted_text=json.loads(json.dumps(document.extracted_text)))
    for page in second_document.extracted_text:
        page['reader']['sha256'] = 'c' * 64  # same source, newly rendered reader
    second = asyncio.run(gemini.analyze_document(second_document, JobMode.BULLET))
    assert len(calls) == 1 and not first.analysis_metadata.cache_hit
    assert second.analysis_metadata.cache_hit and second.analysis_metadata.total_tokens == 0
    evidence = second.output.bullets[0].evidence[0]
    assert evidence.document_id == 99 and evidence.reader_version == 'c' * 64
    assert list(settings.STORAGE_DIR.rglob('*.json'))


def test_cache_is_scoped_by_owner_mode_budget_and_model(document, api, monkeypatch):
    state, calls = api
    state['response'] = response()
    asyncio.run(gemini.analyze_document(document, JobMode.BULLET))
    asyncio.run(gemini.analyze_document(replace(document, owner_id=124), JobMode.BULLET))
    monkeypatch.setattr(settings, 'GEMINI_MAX_OUTPUT_TOKENS', 768)
    asyncio.run(gemini.analyze_document(document, JobMode.BULLET))
    monkeypatch.setattr(settings, 'GEMINI_MODEL', 'gemini-2.5-flash-lite')
    asyncio.run(gemini.analyze_document(document, JobMode.BULLET))
    state['response'] = response('table')
    asyncio.run(gemini.analyze_document(document, JobMode.TABLE))
    assert len(calls) == 5
    assert json.loads(calls[3].content)['generationConfig']['thinkingConfig'] == {'thinkingBudget': 256}


def test_missing_key_and_textless_pages_make_no_network_calls(document, api, monkeypatch):
    _, calls = api
    empty = replace(document, extracted_text=[{**document.extracted_text[0], 'text': '', 'positions': []}])
    result = asyncio.run(gemini.analyze_document(empty, JobMode.CONCEPT))
    assert result.output.concepts == [] and result.warnings == ['no_text_layer']
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', SecretStr(''))
    result = asyncio.run(processing.process_document(document, JobMode.BULLET))
    assert result.analysis_status == 'not_configured' and not calls


def test_unknown_source_id_never_gets_a_verified_citation(document, api):
    state, _ = api
    state['response'] = response(source=999)
    result = asyncio.run(gemini.analyze_document(document, JobMode.BULLET))
    assert result.output.bullets[0].unverified and result.output.bullets[0].evidence == []
    assert 'unverified_claims' in result.warnings


def test_gemini_preserves_multiple_excerpt_ids_and_same_text_on_different_pages(document, api):
    state, calls = api
    document.extracted_text[0]['text'] = 'Another source for the same late fee 0.05% per day.'
    # Repeat a passage on another physical page; send its text only once.
    extra = {**document.extracted_text[1], 'page': 3}
    document.extracted_text.append(extra)
    state['response'] = response(source=[0, 1, 0])
    result = asyncio.run(gemini.analyze_document(document, JobMode.BULLET))
    claim = result.output.bullets[0]
    assert not claim.unverified
    assert [source.page for source in claim.evidence] == [1, 2, 3]
    assert len(calls) == 1
    body = json.loads(calls[0].content)
    assert len(json.loads(body['contents'][0]['parts'][0]['text'])) == 2
    schema = body['generationConfig']['responseFormat']['text']['schema']
    assert schema['$defs']['WireClaim']['properties']['s']['anyOf'][0]['type'] == 'array'


def test_unknown_gemini_source_does_not_discard_its_other_valid_sources(document, api):
    state, _ = api
    state['response'] = response(source=[0, 999])
    result = asyncio.run(gemini.analyze_document(document, JobMode.BULLET))
    claim = result.output.bullets[0]
    assert claim.unverified and [source.page for source in claim.evidence] == [2]


def test_source_budget_keeps_offsets_balances_late_pages_and_reports_truncation():
    pages = [{'page': i, 'text': f'Page {i}: ' + (f'word{i} ' * 300)} for i in range(1, 31)]
    selected, wire, truncated = gemini.select_excerpts(pages, 'bullet', 8000)
    assert len(json.dumps(wire, ensure_ascii=False, separators=(',', ':'))) <= 8000
    assert truncated and any(excerpt.page == 30 for excerpt in selected.values())
    for excerpt in selected.values():
        assert pages[excerpt.page - 1]['text'][excerpt.start:excerpt.end] == excerpt.text
    _, deduped, omitted = gemini.select_excerpts([{'page': 1, 'text': 'Same header'},
                                                {'page': 2, 'text': 'Same header'}], 'bullet', 8000)
    assert deduped == [[0, 'Same header']] and not omitted


def test_table_budget_prioritizes_financial_clause_over_unrelated_text():
    pages = [{'page': 1, 'text': 'Introduction ' * 200 + '\nLate fee 0.05% per day.'}]
    _, wire, truncated = gemini.select_excerpts(pages, 'table', 100)
    assert wire == [[0, 'Late fee 0.05% per day.']] and truncated


@pytest.mark.parametrize('status, code', [(400, 'gemini_configuration_error'), (401, 'gemini_configuration_error'),
                                        (403, 'gemini_configuration_error'), (429, 'gemini_quota_exceeded'),
                                        (503, 'gemini_unavailable')])
def test_api_errors_are_sanitized_and_do_not_retry_or_cache(document, api, status, code):
    state, calls = api
    state.update(status=status, response={'error': {'message': 'test-only-secret-never-live private document'}})
    with pytest.raises(gemini.GeminiAnalysisError) as error:
        asyncio.run(gemini.analyze_document(document, JobMode.BULLET))
    assert error.value.code == code and 'private' not in str(error.value) and 'secret' not in str(error.value)
    assert len(calls) == 1 and not list(settings.STORAGE_DIR.rglob('*.json'))


@pytest.mark.parametrize('payload, code', [
    ({'candidates': []}, 'gemini_invalid_response'),
    ({'promptFeedback': {'blockReason': 'SAFETY'}}, 'gemini_blocked'),
    ({'candidates': [{'finishReason': 'MAX_TOKENS'}]}, 'gemini_output_limit'),
    ({'candidates': [{'finishReason': 'SAFETY'}]}, 'gemini_blocked'),
    ({'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': 'broken JSON'}]}}]}, 'gemini_invalid_response'),
    ({'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': '{}'}]}}]}, 'gemini_invalid_response'),
])
def test_blocked_truncated_or_invalid_output_is_never_a_success(document, api, payload, code):
    state, calls = api
    state['response'] = payload
    with pytest.raises(gemini.GeminiAnalysisError) as error:
        asyncio.run(gemini.analyze_document(document, JobMode.BULLET))
    assert error.value.code == code and len(calls) == (1 if code == 'gemini_blocked' else 2)
    assert not list(settings.STORAGE_DIR.rglob('*.json'))


def test_http_timeout_remains_compatible_with_existing_retry_logic(document, api):
    state, calls = api
    state['exception'] = httpx.ReadTimeout('private request')
    with pytest.raises(TimeoutError):
        asyncio.run(gemini.analyze_document(document, JobMode.BULLET))
    assert len(calls) == 1


def test_oversized_bullet_wire_is_rejected_before_it_can_be_cached(document, api):
    state, calls = api
    raw = {'label': None, 'confidence': None,
           'bullets': [{'t': 'a ' * 399, 's': [0]}] * 3, 'actions': []}
    state['response'] = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(raw)}]}}]}
    with pytest.raises(gemini.GeminiAnalysisError) as error:
        asyncio.run(gemini.analyze_document(document, JobMode.BULLET))
    assert error.value.code == 'gemini_invalid_response' and len(calls) == 2
    assert not list(settings.STORAGE_DIR.rglob('*.json'))


@pytest.mark.parametrize('first', ['malformed_json', 'too_many_concepts', 'word_budget'])
def test_invalid_first_draft_is_corrected_once_and_only_valid_results_are_cached(document, api, first):
    state, calls = api
    mode = JobMode.CONCEPT if first == 'too_many_concepts' else JobMode.BULLET
    async def handler(request):
        if len(calls) > 1:
            return httpx.Response(200, json=response(mode.value))
        if first == 'malformed_json':
            text = '{unfinished'
        elif first == 'too_many_concepts':
            text = json.dumps({'label': None, 'confidence': None, 'concepts': [
                {'n': f'Concept {i}', 't': 'Late fee 0.05% per day.', 's': [0]} for i in range(6)]})
        else:
            text = json.dumps({'label': None, 'confidence': None,
                'bullets': [{'t': 'a ' * 399, 's': [0]}] * 3, 'actions': []})
        return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': text}]}}]})
    state['handler'] = handler
    result = asyncio.run(gemini.analyze_document(document, mode))
    assert result.analysis_status == 'completed' and len(calls) == 2
    assert list(settings.STORAGE_DIR.rglob('*.json'))
    if mode == JobMode.CONCEPT:
        assert len(result.output.concepts) <= 5
        config = json.loads(calls[0].content)['generationConfig']
        schema = config['responseFormat']['text']['schema']
        assert schema['properties']['concepts']['maxItems'] == 5


def test_groq_input_budget_is_independent_of_gemini_budget(monkeypatch):
    monkeypatch.setattr(settings, 'GEMINI_MAX_INPUT_CHARS', 24000)
    monkeypatch.setattr(settings, 'GROQ_MAX_INPUT_CHARS', 8000)
    token = gemini._provider.set('groq')
    try:
        assert gemini.input_budget() == 8000
    finally:
        gemini._provider.reset(token)
    assert gemini.input_budget() == 24000


def test_many_source_topics_do_not_force_more_than_five_concepts():
    from app.services.summary_quality import coverage_instructions, quality_issues
    names = ['AAA', 'BBB', 'CCC', 'DDD', 'EEE', 'FFF']
    wire = [(i, f'Method ({name})\nThis method extracts local spatial patterns from the original input data.')
            for i, name in enumerate(names)]
    raw = gemini.WireConcepts.model_validate({'label': None, 'confidence': None, 'concepts': [
        {'n': name, 't': 'This method extracts local spatial patterns from the original input data.', 's': [i]}
        for i, name in enumerate(names[:3])]})
    assert '3-5' in coverage_instructions(wire, 'concept')
    assert quality_issues(raw, wire, 'concept') == []


@pytest.mark.parametrize('limitation', ['', '   '])
def test_empty_optional_limitation_does_not_fail_an_otherwise_valid_analysis(document, api, limitation):
    state, calls = api
    payload = response()
    raw = json.loads(payload['candidates'][0]['content']['parts'][0]['text'])
    raw['limitation'] = limitation
    payload['candidates'][0]['content']['parts'][0]['text'] = json.dumps(raw)
    state['response'] = payload
    result = asyncio.run(gemini.analyze_document(document, JobMode.BULLET))
    assert result.analysis_status == 'completed' and len(calls) == 1
    assert result.output.limitation


def test_inflight_gemini_request_is_cancelled_before_retry(document, api):
    started, finished = [], []
    async def hanging(_):
        started.append(True)
        try:
            await asyncio.Event().wait()
        finally:
            finished.append(True)
    state, calls = api
    state['handler'] = hanging
    async def run():
        task = asyncio.create_task(gemini.analyze_document(document, JobMode.BULLET))
        while not started:
            await asyncio.sleep(.001)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(run())
    assert finished == [True] and len(calls) == 1
    assert not list(settings.STORAGE_DIR.rglob('*.json'))


@pytest.mark.parametrize('language', ['en', 'vi'])
def test_real_upload_job_saves_gemini_result_and_citations_without_repeat_on_reload(client, session_factory, tmp_path, api, language):
    state, calls = api
    state['response'] = response('table')
    source = make_pdf(tmp_path / 'contract.pdf', [b'BT /F1 12 Tf 72 720 Td (Late fee 0.05% per day.) Tj ET'])
    uploaded = client.post('/upload', data={'mode': 'table', 'language': language}, files=[('files', ('contract.pdf', source.read_bytes(), 'application/pdf'))])
    job_id = int(uploaded.json()['jobId'])
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'completed' and saved['completed_count'] == 1
    file = saved['job_files'][0]
    result = saved['result_data']['documents'][str(file['document_id'])]
    assert saved['result_data']['language'] == language and result['language'] == language
    assert result['analysis_status'] == 'completed' and result['analysis_metadata']['provider'] == 'gemini'
    assert result['output']['penalty']['evidence'][0]['quote'] == 'Late fee 0.05% per day.'
    assert result['label']['ai_label'] == 'Hợp đồng' and len(saved['citations']) == 1
    assert client.get(result['reader']['url']).status_code == 200
    processing.process_job(job_id, session_factory)
    assert client.get(f'/jobs/{job_id}').json() == saved and len(calls) == 1

    # Viewing either UI language reads exactly the saved content, without new model requests.
    for ui_language in ('en', 'vi'):
        headers = {'X-DocuMind-Language': ui_language}
        assert client.get(f'/jobs/{job_id}', headers=headers).json() == saved
        summary = client.get(f"/documents/{file['document_id']}/summary", headers=headers).json()
        assert summary['document'] == result
    assert len(calls) == 1


def test_quota_failure_updates_correct_file_without_false_success(client, session_factory, tmp_path, api):
    state, calls = api
    state.update(status=429, response={'error': {'message': 'quota'}})
    source = make_pdf(tmp_path / 'quota.pdf', [b'BT /F1 12 Tf 72 720 Td (Contract) Tj ET'])
    uploaded = client.post('/upload', files=[('files', ('quota.pdf', source.read_bytes(), 'application/pdf'))])
    job_id = int(uploaded.json()['jobId'])
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == saved['job_files'][0]['status'] == 'failed'
    assert saved['completed_count'] == 0 and saved['result_data']['language'] == 'vi' and saved['result_data']['documents'] == {} and saved['citations'] == []
    assert 'gemini_quota_exceeded' in saved['job_files'][0]['error_message']
    assert saved['job_files'][0]['attempt_count'] == 1 and len(calls) == 1


@pytest.mark.parametrize('language', ['en', 'vi'])
def test_selected_language_controls_prompt_fallback_and_cache(document, api, language):
    state, calls = api
    state['response'] = response()
    source = replace(document, language=language)
    result = asyncio.run(processing.process_document(source, JobMode.BULLET))
    prompt = json.loads(calls[0].content)['systemInstruction']['parts'][0]['text']
    assert ('in English' if language == 'en' else 'in Vietnamese') in prompt
    assert ('The document' if language == 'en' else 'Tài liệu') in result.output.limitation
    asyncio.run(processing.process_document(source, JobMode.BULLET))
    assert len(calls) == 1
    asyncio.run(processing.process_document(replace(source, language='vi' if language == 'en' else 'en'), JobMode.BULLET))
    assert len(calls) == 2
