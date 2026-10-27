"""Groq network recovery without live requests or real credentials."""
import asyncio
import json
import logging
import socket
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.models import Job
from app.services import groq_analysis as groq, processing
from app.services.gemini_analysis import GeminiAnalysisError


@pytest.fixture
def transport(monkeypatch):
    monkeypatch.setattr(settings, 'GROQ_API_KEY', SecretStr('isolated-groq-test-key'))
    monkeypatch.setattr(settings, 'GROQ_MODEL', 'openai/gpt-oss-20b')
    monkeypatch.setattr(settings, 'GROQ_REQUEST_TIMEOUT_SECONDS', 10)
    calls, delays = [], []
    state = {}
    async def handler(request):
        calls.append(request)
        return await state['handler'](request)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(groq.httpx, 'AsyncClient', lambda **kwargs:
                        real_client(transport=httpx.MockTransport(handler), **kwargs))
    async def backoff(seconds):
        delays.append(seconds)
        await asyncio.sleep(0)
    # Patch only this module's reference; real asyncio remains available to
    # simulate a stalled server and check cancellation/deadline behavior.
    monkeypatch.setattr(groq, 'asyncio', SimpleNamespace(timeout=asyncio.timeout, sleep=backoff))
    return state, calls, delays


def body():
    return {'systemInstruction': {'parts': [{'text': 'Return valid JSON.'}]},
            'contents': [{'role': 'user', 'parts': [{'text': 'private source passage'}]}],
            'generationConfig': {'maxOutputTokens': 512, 'responseJsonSchema': {
                'type': 'object', 'properties': {'bullets': {'type': 'array', 'items': {'type': 'string'}}}}}}


def success():
    return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
        'content': json.dumps({'bullets': ['Summary']})}}],
        'usage': {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30}})


@pytest.mark.parametrize('error_type', [httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError])
def test_transient_network_error_recovers_with_same_payload(transport, error_type):
    state, calls, delays = transport
    async def handler(request):
        if len(calls) < 3:
            raise error_type('transient failure', request=request)
        return success()
    state['handler'] = handler
    result, usage = asyncio.run(groq.generate_groq(body()))
    assert result == {'bullets': ['Summary']}
    assert usage['totalTokenCount'] == 30
    assert len(calls) == 3 and delays == [.5, 1.0]
    assert len({request.content for request in calls}) == 1


def test_exhausted_connection_logs_diagnostic_codes_without_keys_or_passages(transport, caplog):
    state, calls, delays = transport
    async def handler(request):
        try:
            raise socket.gaierror(11001, 'isolated-groq-test-key private source passage')
        except OSError as cause:
            raise httpx.ConnectError('isolated-groq-test-key', request=request) from cause
    state['handler'] = handler
    with caplog.at_level(logging.WARNING, logger=groq.__name__):
        with pytest.raises(GeminiAnalysisError) as error:
            asyncio.run(groq.generate_groq(body()))
    assert error.value.code == 'groq_connection_failed'
    assert '3 attempt(s)' in str(error.value)
    assert len(calls) == 3 and delays == [.5, 1.0]
    assert 'gaierror(errno=11001)' in caplog.text
    assert 'isolated-groq-test-key' not in caplog.text + str(error.value)
    assert 'private source passage' not in caplog.text + str(error.value)


@pytest.mark.parametrize('status,code', [(400, 'groq_configuration_error'), (401, 'groq_configuration_error'),
    (403, 'groq_configuration_error'), (422, 'groq_configuration_error'), (429, 'groq_quota_exceeded')])
def test_configuration_and_quota_failures_are_not_retried(transport, status, code):
    state, calls, delays = transport
    async def handler(request):
        return httpx.Response(status, json={'error': {'message': 'Unavailable'}})
    state['handler'] = handler
    with pytest.raises(GeminiAnalysisError) as error:
        asyncio.run(groq.generate_groq(body()))
    assert error.value.code == code
    assert len(calls) == 1 and delays == []


def test_request_timeout_remains_a_timeout_for_the_existing_job_retry(transport):
    state, calls, delays = transport
    async def handler(request):
        raise httpx.ReadTimeout('stalled', request=request)
    state['handler'] = handler
    with pytest.raises(TimeoutError, match='Groq request timed out'):
        asyncio.run(groq.generate_groq(body()))
    assert len(calls) == 1 and delays == []


def test_retries_share_one_overall_deadline(transport, monkeypatch):
    state, calls, delays = transport
    monkeypatch.setattr(settings, 'GROQ_REQUEST_TIMEOUT_SECONDS', .05)
    async def handler(request):
        if len(calls) == 1:
            raise httpx.ConnectError('transient', request=request)
        await asyncio.sleep(10)
        return success()
    state['handler'] = handler
    with pytest.raises(TimeoutError, match='Groq request timed out'):
        asyncio.run(groq.generate_groq(body()))
    assert len(calls) == 2 and delays == [.5]


def test_job_cancellation_does_not_trigger_another_request(transport):
    state, calls, delays = transport
    async def scenario():
        entered = asyncio.Event()
        async def handler(request):
            entered.set()
            await asyncio.Event().wait()
        state['handler'] = handler
        task = asyncio.create_task(groq.generate_groq(body()))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(scenario())
    assert len(calls) == 1 and delays == []


def test_exhausted_network_failure_does_not_publish_a_successful_job(transport, client, session_factory):
    state, calls, delays = transport
    async def handler(request):
        raise httpx.ConnectError('offline', request=request)
    state['handler'] = handler
    response = client.post('/upload', files=[('files', ('source.pdf', b'fixture', 'application/pdf'))])
    assert response.status_code == 202
    job_id = int(response.json()['jobId'])
    async def processor(source, mode):
        return await groq.generate_groq(body())
    processing.process_job(job_id, session_factory, processor=processor)
    with session_factory() as db:
        job = db.get(Job, job_id)
        assert job.status.value == 'failed'
        assert job.completed_count == 0
        assert job.job_files[0].status.value == 'failed'
        assert 'groq_connection_failed' in job.job_files[0].error_message
        assert not job.result_data['documents']
    assert len(calls) == 3


def test_recovered_groq_response_still_maps_to_real_document_evidence(transport, monkeypatch, tmp_path):
    from app.models import FileFormat, JobMode
    from app.services.pdf_extraction import extract_pdf
    from test_pdf_extraction import make_pdf

    state, calls, _ = transport
    monkeypatch.setattr(settings, 'ANALYSIS_PROVIDER', 'groq')
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', SecretStr(''))
    monkeypatch.setattr(settings, 'GEMINI_CACHE_ENABLED', False)
    pdf = make_pdf(tmp_path / 'source.pdf', [b'BT /F1 12 Tf 72 720 Td (Late fee 0.05% per day.) Tj ET'])
    pages = extract_pdf(pdf)['extracted_text']
    for page in pages:
        page['reader'] = {'sha256': 'a' * 64, 'source_sha256': 'b' * 64, 'page_kind': 'page'}
    source = processing.DocumentInput(17, str(pdf), 1, FileFormat.PDF, pages, 123)
    async def handler(request):
        if len(calls) == 1:
            raise httpx.ConnectError('transient', request=request)
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({
            'label': 'Contract', 'confidence': 80,
            'bullets': [{'t': 'Late fee 0.05% per day.', 's': [0]}], 'actions': [], 'limitation': None})}}]})
    state['handler'] = handler
    result = asyncio.run(processing.process_document(source, JobMode.BULLET))
    assert result.analysis_status == 'completed'
    assert result.analysis_metadata.provider == 'groq'
    assert result.output.bullets[0].evidence[0].document_id == 17
    assert result.output.bullets[0].evidence[0].page == 1
    assert len(calls) == 2


@pytest.mark.parametrize('status', [429, 502, 503])
def test_temporary_http_error_respects_retry_after_then_recovers(transport, status):
    state, calls, delays = transport
    async def handler(request):
        if len(calls) == 1:
            return httpx.Response(status, headers={'retry-after': '.25'}, json={'error': {}})
        return success()
    state['handler'] = handler
    result, _ = asyncio.run(groq.generate_groq(body()))
    assert result['bullets'] == ['Summary']
    assert len(calls) == 2 and delays == [.25]


@pytest.mark.parametrize('headers', [
    {'retry-after': '120'}, {'retry-after': 'nan'},
    {'retry-after': '1', 'x-ratelimit-remaining-requests': '0'},
])
def test_long_daily_or_invalid_rate_limit_is_not_spammed_or_reported_as_timeout(transport, headers):
    state, calls, delays = transport
    async def handler(request):
        return httpx.Response(429, headers=headers, json={'error': {}})
    state['handler'] = handler
    with pytest.raises(GeminiAnalysisError) as error:
        asyncio.run(groq.generate_groq(body()))
    assert error.value.code == 'groq_quota_exceeded'
    assert len(calls) == 1 and delays == []


def test_server_failures_have_bounded_retries_without_false_results(transport):
    state, calls, delays = transport
    async def handler(request):
        return httpx.Response(503)
    state['handler'] = handler
    with pytest.raises(GeminiAnalysisError) as error:
        asyncio.run(groq.generate_groq(body()))
    assert error.value.code == 'groq_unavailable'
    assert len(calls) == 3 and delays == [.5, 1.0]


def test_parallel_documents_share_one_groq_request_slot(transport):
    state, calls, _ = transport
    active = peak = 0
    async def handler(request):
        nonlocal active, peak
        active += 1
        peak = max(active, peak)
        await asyncio.sleep(.01)
        active -= 1
        return success()
    state['handler'] = handler
    async def scenario():
        return await asyncio.gather(*(groq.generate_groq(body()) for _ in range(3)))
    assert len(asyncio.run(scenario())) == 3
    assert len(calls) == 3 and peak == 1


def test_real_upload_pipeline_saves_groq_results_and_evidence_on_reload(transport, monkeypatch, tmp_path, client, session_factory):
    from test_pdf_extraction import make_pdf

    state, calls, _ = transport
    monkeypatch.setattr(settings, 'ANALYSIS_PROVIDER', 'groq')
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', SecretStr(''))
    monkeypatch.setattr(settings, 'GEMINI_CACHE_ENABLED', False)
    pdf = make_pdf(tmp_path / 'input.pdf', [b'BT /F1 12 Tf 72 720 Td (Late fee 0.05% per day.) Tj ET'])
    async def handler(request):
        if len(calls) == 1:
            raise httpx.ConnectError('transient', request=request)
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({
            'label': 'Contract', 'confidence': 80,
            'bullets': [{'t': 'Late fee 0.05% per day.', 's': [0]}], 'actions': [], 'limitation': None})}}]})
    state['handler'] = handler
    uploaded = client.post('/upload', files=[('files', ('input.pdf', pdf.read_bytes(), 'application/pdf'))])
    assert uploaded.status_code == 202
    job_id = int(uploaded.json()['jobId'])
    processing.process_job(job_id, session_factory)
    result = client.get(f'/jobs/{job_id}').json()
    assert result['status'] == 'completed' and result['completed_count'] == 1
    document_id = result['job_files'][0]['document_id']
    saved = result['result_data']['documents'][str(document_id)]
    assert saved['analysis_metadata']['provider'] == 'groq'
    assert saved['output']['bullets'][0]['evidence'][0]['document_id'] == document_id
    assert saved['output']['bullets'][0]['evidence'][0]['page'] == 1
    assert client.get(f'/jobs/{job_id}').json()['result_data'] == result['result_data']
    assert len(calls) == 2
