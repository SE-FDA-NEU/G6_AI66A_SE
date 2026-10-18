import json

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.services.search_embeddings import EmbeddingUnavailable, GeminiSearchEmbedder


@pytest.mark.parametrize('task', ['RETRIEVAL_DOCUMENT', 'RETRIEVAL_QUERY'])
def test_embedding_rest_contract_batches_validates_and_hides_key(monkeypatch, task):
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', SecretStr('test-only-never-live'))
    monkeypatch.setattr(settings, 'SEARCH_EMBEDDING_DIMENSIONS', 128)
    calls = []
    def handler(request):
        calls.append(request)
        requests = json.loads(request.content)['requests']
        assert all(item['taskType'] == task and item['outputDimensionality'] == 128 for item in requests)
        assert all('embedContentConfig' not in item for item in requests)
        assert request.headers['x-goog-api-key'] == 'test-only-never-live' and not request.url.query
        return httpx.Response(200, json={'embeddings': [{'values': [1.] + [0.] * 127} for _ in requests]})
    real_client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    vectors = GeminiSearchEmbedder().embed(['passage'] * 51, task=task)
    assert len(vectors) == 51 and len(calls) == 2 and len(vectors[0]) == 128


@pytest.mark.parametrize('response', [
    httpx.Response(500, json={'error': 'private provider response'}),
    httpx.Response(200, json={'embeddings': []}),
    httpx.Response(200, json={'embeddings': [{'values': [0., 0.]}]}),
    httpx.Response(200, json={'embeddings': [{'values': [1., 0.]}]}),
])
def test_provider_errors_and_bad_vectors_are_sanitized(monkeypatch, response):
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', SecretStr('test-only-never-live'))
    real_client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(lambda request: response), **kwargs))
    with pytest.raises(EmbeddingUnavailable, match='temporarily unavailable'):
        GeminiSearchEmbedder().embed(['passage'], task='RETRIEVAL_DOCUMENT')


@pytest.mark.parametrize('delay, expected', [('12.4s', 13), ('NaNs', 60), ('bad', 60)])
def test_quota_is_sanitized_and_preserves_retry_time(monkeypatch, delay, expected):
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', SecretStr('test-only-never-live'))
    response = httpx.Response(429, json={'error': {'message': 'private provider response', 'details': [
        {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': delay}]}})
    real_client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(lambda request: response), **kwargs))
    with pytest.raises(EmbeddingUnavailable) as caught:
        GeminiSearchEmbedder().embed(['passage'], task='RETRIEVAL_QUERY')
    assert caught.value.code == 'embedding_rate_limited'
    assert caught.value.retry_after == expected
    assert 'private' not in str(caught.value)
