"""Transient Gemini recovery without live API calls or real backoff sleeps."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.services import gemini_analysis as gemini, processing
from test_gemini_analysis import api, response, contract_api_job
from test_pdf_extraction import make_pdf


@pytest.fixture
def delays(monkeypatch):
    recorded = []
    async def pause(seconds):
        recorded.append(seconds)
    monkeypatch.setattr(gemini, '_retry_sleep', pause)
    monkeypatch.setattr(gemini.random, 'uniform', lambda low, high: .125)
    return recorded


@pytest.mark.parametrize('status', [408, 500, 502, 503, 504])
def test_temporary_http_failure_recovers_without_exposing_payload(api, delays, caplog, status):
    state, calls = api
    async def handler(request):
        if len(calls) < 3:
            return httpx.Response(status, json={'error': {'message': 'private-secret source text'}})
        return httpx.Response(200, json=response())
    state['handler'] = handler
    with caplog.at_level(logging.WARNING, logger=gemini.__name__):
        result, usage = asyncio.run(gemini.generate({}))
    assert result['label'] == 'Hợp đồng' and usage['totalTokenCount'] == 280
    assert len(calls) == 3 and delays == [1.125, 2.125]
    assert f'status={status}' in caplog.text
    assert 'private-secret' not in caplog.text and 'test-only-secret' not in caplog.text


@pytest.mark.parametrize('error_type', [httpx.ConnectError, httpx.RemoteProtocolError])
def test_network_failure_recovers_with_bounded_attempts(api, delays, error_type):
    state, calls = api
    async def handler(request):
        if len(calls) == 1:
            raise error_type('private-key-and-prompt', request=request)
        return httpx.Response(200, json=response())
    state['handler'] = handler
    assert asyncio.run(gemini.generate({}))[0]['label'] == 'Hợp đồng'
    assert len(calls) == 2 and delays == [1.125]


def test_persistent_failure_stops_after_three_calls(api, delays):
    state, calls = api
    state.update(status=503, response={'error': {}})
    with pytest.raises(gemini.GeminiAnalysisError) as error:
        asyncio.run(gemini.generate({}))
    assert error.value.code == 'gemini_unavailable'
    assert len(calls) == 3 and len(delays) == 2


@pytest.mark.parametrize('status', [400, 401, 402, 403, 404, 429])
def test_permanent_errors_and_unqualified_rate_limits_are_not_retried(api, delays, status):
    state, calls = api
    state.update(status=status, response={'error': {}})
    with pytest.raises(gemini.GeminiAnalysisError):
        asyncio.run(gemini.generate({}))
    assert len(calls) == 1 and delays == []


@pytest.mark.parametrize('status', [429, 503])
def test_short_retry_after_is_honored(api, delays, status):
    state, calls = api
    async def handler(request):
        if len(calls) == 1:
            return httpx.Response(status, headers={'retry-after': '3'}, json={'error': {}})
        return httpx.Response(200, json=response())
    state['handler'] = handler
    asyncio.run(gemini.generate({}))
    assert len(calls) == 2 and delays == [3]


@pytest.mark.parametrize('status', [429, 503])
def test_retry_after_beyond_budget_is_not_ignored(api, delays, status):
    state, calls = api
    async def handler(request):
        return httpx.Response(status, headers={'retry-after': '9999'}, json={'error': {}})
    state['handler'] = handler
    with pytest.raises(gemini.GeminiAnalysisError):
        asyncio.run(gemini.generate({}))
    assert len(calls) == 1 and delays == []


def test_daily_quota_is_not_retried_even_with_retry_header(api, delays):
    state, calls = api
    async def handler(request):
        return httpx.Response(429, headers={'retry-after': '1'}, json={'error': {'details': [
            {'violations': [{'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}]}]}})
    state['handler'] = handler
    with pytest.raises(gemini.GeminiAnalysisError) as error:
        asyncio.run(gemini.generate({}))
    assert error.value.code == 'gemini_daily_quota_exceeded'
    assert len(calls) == 1 and delays == []


@pytest.mark.parametrize('header', ['nan', 'inf', '-1', 'not-a-date'])
def test_invalid_retry_after_is_not_used(header):
    assert gemini.retry_after_seconds(httpx.Response(503, headers={'retry-after': header})) is None


def test_http_date_retry_after_is_supported():
    header = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=30), usegmt=True)
    assert 28 <= gemini.retry_after_seconds(httpx.Response(503, headers={'retry-after': header})) <= 30


def test_backoff_and_requests_share_one_total_deadline(api, monkeypatch):
    state, calls = api
    monkeypatch.setattr(settings, 'GEMINI_REQUEST_TIMEOUT_SECONDS', .02)
    async def handler(request):
        await asyncio.sleep(10)
    state['handler'] = handler
    with pytest.raises(TimeoutError):
        asyncio.run(gemini.generate({}))
    assert len(calls) == 1


def test_deadline_is_not_reset_for_the_second_http_attempt(api, monkeypatch):
    state, calls = api
    monkeypatch.setattr(settings, 'GEMINI_REQUEST_TIMEOUT_SECONDS', .3)
    cancelled = []
    async def handler(request):
        if len(calls) == 1:
            return httpx.Response(503, headers={'retry-after': '.1'})
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)
    state['handler'] = handler
    with pytest.raises(TimeoutError):
        asyncio.run(gemini.generate({}))
    assert len(calls) == 2 and cancelled == [True]


def test_uploaded_job_recovers_from_503_and_persists_grounded_results(client, session_factory, contract_api_job, delays):
    job_id, state, calls = contract_api_job
    successful_handler = state['handler']
    async def intermittent(request):
        if len(calls) < 3:
            return httpx.Response(503, json={'error': {}})
        return await successful_handler(request)
    state['handler'] = intermittent
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'completed' and saved['completed_count'] == 1
    assert saved['citations'] and saved['result_data']['documents']
    assert len(calls) == 3
    assert client.get(f'/jobs/{job_id}').json()['result_data'] == saved['result_data']


@pytest.mark.parametrize('extension', ['pdf', 'docx', 'pptx'])
@pytest.mark.parametrize('recovers', [True, False], ids=['503-then-success', '503-persists'])
def test_uploaded_file_formats_handle_503_without_false_success(
        client, session_factory, api, delays, tmp_path, extension, recovers):
    from docx import Document as WordDocument
    from pptx import Presentation
    from pptx.util import Inches
    from app.models import Document

    text = 'Late fee 0.05% per day.'
    source = tmp_path / f'contract.{extension}'
    if extension == 'pdf':
        make_pdf(source, [f'BT /F1 12 Tf 72 720 Td ({text}) Tj ET'.encode()])
    elif extension == 'docx':
        word = WordDocument()
        word.add_paragraph(text)
        word.save(source)
    else:
        slides = Presentation()
        slide = slides.slides.add_slide(slides.slide_layouts[6])
        slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(1)).text = text
        slides.save(source)
    state, calls = api
    async def handler(request):
        if not recovers or len(calls) < 3:
            return httpx.Response(503, json={'error': {'message': 'Provider temporarily unavailable'}})
        return httpx.Response(200, json=response('table'))
    state['handler'] = handler
    uploaded = client.post('/upload', data={'mode': 'table'}, files=[
        ('files', (source.name, source.read_bytes(), 'application/octet-stream'))])
    assert uploaded.status_code == 202
    job_id = int(uploaded.json()['jobId'])
    processing.process_job(job_id, session_factory)
    saved = client.get(f'/jobs/{job_id}').json()
    assert len(calls) == 3
    file = saved['job_files'][0]
    if recovers:
        assert saved['status'] == file['status'] == 'completed'
        assert saved['completed_count'] == 1 and file['error_message'] is None
        result = saved['result_data']['documents'][str(file['document_id'])]
        assert result['analysis_status'] == 'completed'
        assert saved['citations'][0]['text_span'] == text
        assert client.get(result['reader']['url']).status_code == 200
    else:
        assert saved['status'] == file['status'] == 'failed'
        assert saved['completed_count'] == 0 and 'gemini_unavailable' in file['error_message']
        assert saved['result_data']['documents'] == {} and saved['citations'] == []
    with session_factory() as db:
        from pathlib import Path
        assert Path(db.get(Document, file['document_id']).storage_path).read_bytes() == source.read_bytes()
    processing.process_job(job_id, session_factory)
    assert client.get(f'/jobs/{job_id}').json() == saved and len(calls) == 3


def test_cancellation_during_backoff_stops_retrying(api, monkeypatch):
    state, calls = api
    state.update(status=503, response={})
    async def cancel(delay):
        raise asyncio.CancelledError
    monkeypatch.setattr(gemini, '_retry_sleep', cancel)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(gemini.generate({}))
    assert len(calls) == 1


@pytest.mark.parametrize('code', ['gemini_unavailable', 'gemini_connection_failed'])
@pytest.mark.parametrize('enabled', [False, True])
def test_groq_fallback_is_opt_in_and_restores_provider_context(monkeypatch, code, enabled):
    monkeypatch.setattr(settings, 'ANALYSIS_PROVIDER', 'gemini')
    monkeypatch.setattr(settings, 'GROQ_FALLBACK_ENABLED', enabled)
    monkeypatch.setattr(settings, 'GROQ_API_KEY', SecretStr('test-only-key'))
    providers = []
    async def analyze(document, mode):
        providers.append(gemini._provider.get())
        if providers[-1] == 'gemini':
            raise gemini.GeminiAnalysisError(code, 'Safe failure')
        return 'recovered'
    monkeypatch.setattr(gemini, '_analyze_document', analyze)
    previous = gemini._provider.get()
    if enabled:
        assert asyncio.run(gemini.analyze_document(None, None)) == 'recovered'
        assert providers == ['gemini', 'groq']
    else:
        with pytest.raises(gemini.GeminiAnalysisError):
            asyncio.run(gemini.analyze_document(None, None))
        assert providers == ['gemini']
    assert gemini._provider.get() == previous
