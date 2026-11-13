"""Personal keys stay in worker memory and never share provider credentials."""
import asyncio
import json

import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.models import Job, JobMode
from app.services import gemini_analysis as gemini
from app.services.analysis_credentials import use_gemini_key, user_gemini_key
from app.services.job_queue import JobQueue
from pathlib import Path
from test_gemini_analysis import api, document, response


@pytest.mark.parametrize('key', ['', ' ', 'bad key', 'x' * 257])
def test_upload_requires_personal_key_without_writing_job(client, session_factory, key):
    client.headers.pop('X-Gemini-Api-Key', None)
    headers = {'X-Gemini-Api-Key': key} if key else {}
    result = client.post('/upload', headers=headers, files={'files': ('report.pdf', b'%PDF-test')})
    assert result.status_code == 400
    assert result.json() == {'detail': 'Enter your Gemini API key to analyze documents.'}
    with session_factory() as db:
        assert db.query(Job).count() == 0


def test_upload_passes_key_only_to_queue_not_database_or_response(client, job_queue, session_factory, monkeypatch):
    captured = []
    def enqueue(job_id, *, gemini_api_key):
        captured.append(gemini_api_key)
    monkeypatch.setattr(job_queue, 'enqueue', enqueue)
    result = client.post('/upload', headers={'X-Gemini-Api-Key': 'private-upload-key'},
                         files={'files': ('report.pdf', b'%PDF-test')})
    assert result.status_code == 202
    assert captured[0].get_secret_value() == 'private-upload-key'
    assert 'private-upload-key' not in repr(captured)
    with session_factory() as db:
        job = db.get(Job, int(result.json()['jobId']))
        assert 'private-upload-key' not in json.dumps(job.result_data)
    assert 'private-upload-key' not in client.get(f"/jobs/{result.json()['jobId']}").text
    assert user_gemini_key.get() is None


def test_concurrent_jobs_keep_separate_keys_in_worker_threads():
    seen = {}
    def processor(job_id, factory):
        seen[job_id] = user_gemini_key.get().get_secret_value()
    async def run():
        queue = JobQueue(None, processor=processor)
        first = queue.enqueue(1, gemini_api_key=SecretStr('first-key'))
        second = queue.enqueue(2, gemini_api_key=SecretStr('second-key'))
        await asyncio.gather(first, second)
        assert user_gemini_key.get() is None
        assert not queue.tasks and not queue.jobs
    asyncio.run(run())
    assert seen == {1: 'first-key', 2: 'second-key'}


def test_personal_key_forces_gemini_and_bypasses_cache(api, document, monkeypatch):
    state, calls = api
    state['response'] = response()
    monkeypatch.setattr(settings, 'ANALYSIS_PROVIDER', 'groq')
    async def run():
        with use_gemini_key(SecretStr('personal-key')):
            assert gemini.cache_file(document, {}) is None
            result = await gemini.analyze_document(document, JobMode.BULLET)
            assert result.analysis_metadata.provider == 'gemini'
            assert not result.analysis_metadata.cache_hit
        assert user_gemini_key.get() is None
    asyncio.run(run())
    assert calls and all(call.headers['x-goog-api-key'] == 'personal-key' for call in calls)


def test_invalid_personal_key_never_falls_back_to_shared_key(api, document, monkeypatch, caplog):
    state, calls = api
    state.update(status=403, response={'error': {'message': 'personal-secret'}})
    monkeypatch.setattr(settings, 'GROQ_FALLBACK_ENABLED', True)
    monkeypatch.setattr(settings, 'GROQ_API_KEY', SecretStr('shared-groq-secret'))
    async def run():
        with use_gemini_key(SecretStr('personal-secret')):
            with pytest.raises(gemini.GeminiAnalysisError) as error:
                await gemini.analyze_document(document, JobMode.BULLET)
            assert error.value.code == 'gemini_configuration_error'
        assert user_gemini_key.get() is None
    asyncio.run(run())
    assert len(calls) == 1
    assert 'personal-secret' not in caplog.text


def test_unavailable_personal_api_never_uses_shared_fallback(api, document, monkeypatch):
    state, calls = api
    state.update(status=503, response={'error': {}})
    monkeypatch.setattr(settings, 'GROQ_FALLBACK_ENABLED', True)
    monkeypatch.setattr(settings, 'GROQ_API_KEY', SecretStr('shared-groq-secret'))
    async def pause(seconds):
        pass
    monkeypatch.setattr(gemini, '_retry_sleep', pause)
    async def run():
        with use_gemini_key(SecretStr('personal-key')):
            with pytest.raises(gemini.GeminiAnalysisError) as error:
                await gemini.analyze_document(document, JobMode.BULLET)
            assert error.value.code == 'gemini_unavailable'
    asyncio.run(run())
    assert len(calls) == 3
    assert all(call.headers['x-goog-api-key'] == 'personal-key' for call in calls)


@pytest.mark.parametrize('status', [200, 403])
def test_real_upload_worker_preserves_results_without_persisting_key(client, session_factory, api, document, status):
    state, calls = api
    state.update(status=status, response=response() if status == 200 else {'error': {}})
    uploaded = client.post('/upload', files={'files': ('source.pdf', Path(document.storage_path).read_bytes())})
    assert uploaded.status_code == 202
    job_id = int(uploaded.json()['jobId'])
    async def run():
        queue = JobQueue(session_factory)
        await queue.enqueue(job_id, gemini_api_key=SecretStr('worker-only-key'))
    asyncio.run(run())
    result = client.get(f'/jobs/{job_id}').json()
    assert result['status'] == ('completed' if status == 200 else 'failed')
    assert calls and all(call.headers['x-goog-api-key'] == 'worker-only-key' for call in calls)
    assert 'worker-only-key' not in json.dumps(result)
    if status == 200:
        assert result['result_data']['documents']
    else:
        assert 'gemini_configuration_error' in result['job_files'][0]['error_message']
    count = len(calls)
    assert client.get(f'/jobs/{job_id}').status_code == 200
    assert len(calls) == count
