"""Validate the benchmark harness offline; these tests are NOT a real-model benchmark."""
import json
from pathlib import Path
import sys

from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'test'))
import benchmark_t38
from app.core.config import settings
from app.services import gemini_analysis as gemini
from test_pdf_extraction import make_pdf


def test_harness_measures_extraction_generation_and_persistence_in_isolation(tmp_path, monkeypatch):
    source = benchmark_t38.sample_pdf(tmp_path / 'source.pdf')
    calls = []

    async def fake_generate(body):
        calls.append(body)
        sources = json.loads(body['contents'][0]['parts'][0]['text'])
        actions = [{'t': text, 's': [source_id]} for source_id, text in sources if text.startswith('Recommended action:')]
        return {'label': 'Report', 'confidence': 90, 'bullets': [{'t': sources[0][1], 's': [sources[0][0]]}],
                'actions': actions}, {'promptTokenCount': 100, 'candidatesTokenCount': 100}

    monkeypatch.setattr(settings, 'STORAGE_DIR', tmp_path / 'storage')
    monkeypatch.setattr(settings, 'GEMINI_CACHE_ENABLED', False)
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', SecretStr('offline-harness-test'))
    monkeypatch.setattr(gemini, 'generate', fake_generate)
    report = benchmark_t38.benchmark(source, tmp_path)
    assert report['passed'] and report['status'] == 'completed'
    assert report['page_count'] == 15 and report['action_count'] == 2
    assert report['within_target'] and report['field_evidence_valid']
    assert report['analysis_metadata']['cache_hit'] is False and len(calls) == 1


def test_missing_real_key_is_explicitly_blocked_not_reported_as_a_success(tmp_path, monkeypatch):
    output = tmp_path / 'report.json'
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', SecretStr(''))
    monkeypatch.setattr(sys, 'argv', ['benchmark_t38.py', '--output', str(output)])
    assert benchmark_t38.main() == 1
    report = json.loads(output.read_text(encoding='utf-8'))
    assert report['status'] == 'blocked' and not report['passed'] and not report['real_model']


def test_wrong_page_count_does_not_spend_model_quota(tmp_path, monkeypatch):
    source = make_pdf(tmp_path / 'one-page.pdf', [b''])
    report = benchmark_t38.benchmark(source, tmp_path)
    assert report['status'] == 'blocked' and not report['passed'] and report['page_count'] == 1
