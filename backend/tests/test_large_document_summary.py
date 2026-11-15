import asyncio
from dataclasses import replace
import json
import httpx
import pytest
from pydantic import SecretStr
from app.core.config import settings
from app.models import FileFormat, JobMode
from app.services import gemini_analysis as gemini, processing
from app.services.analysis_credentials import user_gemini_key
from app.services.summary_quality import coverage_targets, quality_issues


def long_document():
    pages = [{'page': i, 'text': f'Page {i}. ' + ('The source explains the documented mechanism and its effects. ' * 12),
              'reader': {'sha256': 'a' * 64}} for i in range(1, 81)]
    return processing.DocumentInput(11, '/unused', 80, FileFormat.PDF, pages, 7, 'en')


def provider(calls, failures=None):
    async def generate(body):
        payload = json.loads(body['contents'][0]['parts'][0]['text'])
        mapping = isinstance(payload[0][0], int)
        compact = 'ONE PART' in body['systemInstruction']['parts'][0]['text']
        calls.append((mapping, compact, payload))
        if not mapping and not compact and failures and failures.pop():
            raise TimeoutError('Transient reduce timeout')
        items = (payload[0], payload[-1])
        claims = [{'t': text[:120], 's': [source] if mapping else source} for source, text in items]
        return {'label': None, 'confidence': None, 'bullets': claims, 'actions': []}, {'promptTokenCount': 10, 'candidatesTokenCount': 5, 'totalTokenCount': 15}
    return generate


def test_maps_cover_all_pages_and_every_reduction_request_is_bounded(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'GEMINI_MAX_INPUT_CHARS', 2000)
    monkeypatch.setattr(settings, 'GEMINI_CACHE_ENABLED', False)
    calls = []
    monkeypatch.setattr(gemini, 'generate', provider(calls))
    result = asyncio.run(gemini.analyze_document(long_document(), JobMode.BULLET))
    pages = {int(text.split('.')[0].split()[1]) for mapping, _, payload in calls if mapping for _, text in payload if text.startswith('Page ')}
    assert pages == set(range(1, 81))
    assert any(not mapping and compact for mapping, compact, _ in calls)
    assert all(len(json.dumps(payload, ensure_ascii=False, separators=(',', ':'))) <= 2000 for _, _, payload in calls)
    cited = {e.page for c in result.output.bullets for e in c.evidence}
    assert {1, 80} <= cited and not result.analysis_metadata.input_truncated


def test_personal_chunks_survive_retry_only_within_the_same_job(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'GEMINI_MAX_INPUT_CHARS', 2000)
    monkeypatch.setattr(settings, 'STORAGE_DIR', tmp_path)
    calls = []
    monkeypatch.setattr(gemini, 'generate', provider(calls, [False, True]))
    source = long_document()
    async def run():
        token = user_gemini_key.set(SecretStr('private-test-key'))
        try:
            with pytest.raises(TimeoutError):
                await gemini.analyze_document(source, JobMode.BULLET)
            before = sum(mapping for mapping, _, _ in calls)
            assert (await gemini.analyze_document(source, JobMode.BULLET)).output.bullets
            assert sum(mapping for mapping, _, _ in calls) == before
        finally:
            user_gemini_key.reset(token)
    asyncio.run(run())
    assert source.analysis_cache and not list(tmp_path.rglob('*.json'))
    assert not long_document().analysis_cache
    assert replace(source, page_count=81).analysis_cache is source.analysis_cache


def test_output_limit_repair_expands_tokens(monkeypatch):
    calls = []
    async def generate(body):
        calls.append(body['generationConfig']['maxOutputTokens'])
        if len(calls) == 1:
            raise gemini.GeminiAnalysisError('gemini_output_limit', 'Truncated')
        return {'label': None, 'confidence': None, 'bullets': [{'t': 'A supported finding.', 's': [0]}], 'actions': []}, {}
    monkeypatch.setattr(gemini, 'generate', generate)
    wire = [[0, 'A supported finding.']]
    raw, _ = asyncio.run(gemini.generate_validated(gemini.request_body('bullet', wire, 'en'), wire, 'bullet'))
    assert calls == [settings.GEMINI_MAX_OUTPUT_TOKENS, min(16384, settings.GEMINI_MAX_OUTPUT_TOKENS * 2)]
    assert raw.bullets[0].s == [0]


def test_google_retry_info_and_daily_quota():
    r = httpx.Response(429, json={'error': {'details': [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '23.5s'}]}})
    assert gemini.retry_after_seconds(r) == 23.5
    assert gemini.daily_quota(httpx.Response(429, json={'error': {'details': [{'violations': [{'quotaId': 'RequestsPerDay'}]}]}}))


def test_many_topics_fit_the_existing_sixteen_item_summary_contract():
    wire = [[i, f'Topic {i // 2}\nThis subject defines the mechanism and explains its practical effects.'] for i in range(100)]
    targets = coverage_targets(wire, 'bullet')
    assert len(targets) == 15 and targets[0]['name'] == 'Topic 0' and targets[-1]['name'] == 'Topic 49'
    raw = gemini.WireBullet(label=None, confidence=None, actions=[], bullets=[gemini.WireClaim(t='An overview.', s=[0])] + [
        gemini.WireClaim(t=t['name'] + ' defines the underlying mechanism and explains its practical effects.', s=[t['sources'][0]]) for t in targets])
    assert quality_issues(raw, wire, 'bullet') == []



@pytest.mark.parametrize('mode, target_name', [('bullet', 'BULLET_TARGET_SECONDS'), ('table', 'TABLE_TARGET_SECONDS')])
def test_large_sources_still_obey_BR_workflow_deadlines(client, session_factory, monkeypatch, mode, target_name):
    from app.models import Job
    count = 5 if mode == 'table' else 1
    response = client.post('/upload', data={'mode': mode}, files=[
        ('files', (f'large-{i}.pdf', b'sample', 'application/pdf')) for i in range(count)])
    assert response.status_code == 202
    job_id = int(response.json()['jobId'])
    with session_factory() as db:
        for file in db.get(Job, job_id).job_files:
            file.document.page_count = 15
            file.document.extracted_text = long_document().extracted_text
        db.commit()
    monkeypatch.setattr(processing, target_name, .02)
    cancelled = []
    async def analyze(document, mode):
        try:
            await asyncio.sleep(.1)
            return {'summary': 'Must never publish late.'}
        finally:
            cancelled.append(document.id)
    processing.process_job(job_id, session_factory, analyze)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'failed' and saved['completed_count'] == 0
    assert saved['result_data']['documents'] == {} and cancelled
    assert all('0.02-second target' in f['error_message'] for f in saved['job_files'])


def test_provider_timeout_keeps_its_identity_after_job_retries(client, session_factory):
    from app.models import Job
    response = client.post('/upload', data={'mode': 'bullet'}, files=[
        ('files', ('source.pdf', b'sample', 'application/pdf'))])
    job_id = int(response.json()['jobId'])
    with session_factory() as db:
        document = db.get(Job, job_id).job_files[0].document
        document.page_count = 1
        document.extracted_text = [{'page': 1, 'text': 'Source content.'}]
        db.commit()
    async def timeout(document, mode):
        raise gemini.GeminiRequestTimeout('Gemini request exceeded 45 seconds.')
    processing.process_job(job_id, session_factory, timeout)
    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'failed'
    file = saved['job_files'][0]
    assert file['attempt_count'] == 3
    assert file['error_message'] == 'gemini_request_timeout: Gemini request exceeded 45 seconds.'


def test_content_quality_does_not_reject_or_rewrite_provider_output(monkeypatch):
    import app.services.summary_quality as quality
    def forbidden(*args):
        pytest.fail('Content quality must not gate provider output')
    monkeypatch.setattr(quality, 'quality_issues', forbidden)
    calls = []
    async def generate(body):
        calls.append(body)
        return {'label': None, 'confidence': None, 'bullets': [
            {'t': 'The source briefly describes the subject.', 's': [0]}], 'actions': []}, {}
    monkeypatch.setattr(gemini, 'generate', generate)
    wire = [[0, 'GAN\nA generative adversarial network learns from a discriminator.'],
            [1, 'CNN\nA convolutional network applies convolutional filters.']]
    raw, _ = asyncio.run(gemini.generate_validated(gemini.request_body('bullet', wire, 'en'), wire, 'bullet'))
    assert len(calls) == 1
    assert raw.bullets[0].t == 'The source briefly describes the subject.'
