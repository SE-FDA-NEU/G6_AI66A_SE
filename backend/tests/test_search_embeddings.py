from collections import Counter
from copy import deepcopy
import json

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.core.security import create_access_token
from app.models import Document
from app.services.search_embeddings import EmbeddingUnavailable, GeminiSearchEmbedder
from test_cross_document_search import add_document, search_corpus


@pytest.mark.parametrize('task', ['RETRIEVAL_DOCUMENT', 'RETRIEVAL_QUERY'])
@pytest.mark.parametrize('count', [20, 21, 50, 51])
def test_embedding_rest_contract_batches_validates_and_hides_key(monkeypatch, task, count):
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', SecretStr('test-only-never-live'))
    monkeypatch.setattr(settings, 'SEARCH_EMBEDDING_DIMENSIONS', 128)
    calls = []
    def handler(request):
        calls.append(request)
        requests = json.loads(request.content)['requests']
        assert all(item['taskType'] == task and item['outputDimensionality'] == 128 for item in requests)
        assert all('embedContentConfig' not in item for item in requests)
        assert request.headers['x-goog-api-key'] == 'test-only-never-live' and not request.url.query
        return httpx.Response(200, json={'embeddings': [
            {'values': [float(item['content']['parts'][0]['text'].split()[-1]) + 1, 1.] + [0.] * 126}
            for item in requests]})
    real_client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    texts = [f'Document passage {number}' for number in range(count)]
    vectors = GeminiSearchEmbedder().embed(texts, task=task)
    assert len(vectors) == count and len(calls) == (count + 49) // 50
    batches = [json.loads(call.content)['requests'] for call in calls]
    assert [len(batch) for batch in batches] == [min(50, count - start) for start in range(0, count, 50)]
    assert [item['content']['parts'][0]['text'] for batch in batches for item in batch] == texts
    for number, vector in enumerate(vectors):
        assert len(vector) == 128 and sum(value * value for value in vector) == pytest.approx(1.)
        assert vector[0] / vector[1] == pytest.approx(number + 1)


@pytest.fixture
def corpus_embedding_api(monkeypatch):
    """Mock only HTTP; use the real embedder, validation, ranking and JSON caches."""
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', SecretStr('offline-us02-never-live'))
    monkeypatch.setattr(settings, 'SEARCH_EMBEDDING_MODEL', 'offline-us02-model')
    monkeypatch.setattr(settings, 'SEARCH_EMBEDDING_DIMENSIONS', 128)
    state = {'calls': [], 'invalid_index': None}

    def handler(request):
        assert request.url.host == 'generativelanguage.googleapis.com'
        assert request.url.path.endswith('/offline-us02-model:batchEmbedContents')
        assert request.headers['x-goog-api-key'] == 'offline-us02-never-live' and not request.url.query
        batch = json.loads(request.content)['requests']
        state['calls'].append(batch)
        vectors = []
        for number, item in enumerate(batch):
            assert item['model'] == 'models/offline-us02-model' and item['outputDimensionality'] == 128
            text = item['content']['parts'][0]['text']
            relevant = item['taskType'] == 'RETRIEVAL_QUERY' or 'Amber escrow release' in text
            vector = [3., 4., 0.] if relevant else [0., 0., 5.]
            vector += [0.] * 125
            if item['taskType'] == 'RETRIEVAL_DOCUMENT' and number == state['invalid_index']:
                vector = [0.] * 128
            vectors.append({'values': vector})
        return httpx.Response(200, json={'embeddings': vectors})

    real_client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs:
                        real_client(transport=httpx.MockTransport(handler), **kwargs))
    return state


def embedded_texts(state, task):
    return [item['content']['parts'][0]['text'] for batch in state['calls']
            for item in batch if item['taskType'] == task]


def test_semantic_http_search_paginates_more_than_twenty_and_isolates_owner_caches(
        client, session_factory, search_corpus, corpus_embedding_api):
    """TC-US02-07: real embedding adapter, deterministic relevance and cross-account caches."""
    state = corpus_embedding_api
    params = {'q': 'signed handover requirement', 'mode': 'semantic'}
    assert client.get('/search', params={'q': params['q']}).json()['hits'] == []
    first = client.get('/search', params=params)
    assert first.status_code == 200
    assert first.json()['total_hits'] == 21 and len(first.json()['hits']) == 20
    tail = client.get('/search', params={**params, 'offset': 20}).json()
    assert tail['total_hits'] == 21 and len(tail['hits']) == 1
    full = client.get('/search', params={**params, 'limit': 100}).json()
    assert first.json()['hits'] + tail['hits'] == full['hits']
    assert {hit['document_id'] for hit in full['hits']} == set(search_corpus['relevant'])
    for hit in full['hits']:
        assert hit['page'] == 3 and hit['score'] == pytest.approx(1.)
        assert hit['snippet'] == search_corpus['pages'][hit['document_id']][2]
        assert hit['doc_name'] == search_corpus['names'][hit['document_id']]
    expected_texts = [text for document_id in search_corpus['owned']
                      for text in search_corpus['pages'][document_id] if text]
    assert Counter(embedded_texts(state, 'RETRIEVAL_DOCUMENT')) == Counter(expected_texts)
    assert [len(batch) for batch in state['calls'] if batch[0]['taskType'] == 'RETRIEVAL_DOCUMENT'] == [50]
    assert embedded_texts(state, 'RETRIEVAL_QUERY') == [params['q']] * 3
    with session_factory() as db:
        own_cache = {document.id: deepcopy(document.extracted_text)
                     for document in db.query(Document).filter_by(owner_id=123)}
        for pages in own_cache.values():
            for page in pages:
                if not page['text']:
                    assert 'search' not in page
                    continue
                assert page['search']['model'] == 'offline-us02-model:128'
                for vector in page['search']['passages'].values():
                    assert len(vector) == 128 and sum(value * value for value in vector) == pytest.approx(1.)
        assert all('search' not in page for document_id in search_corpus['peer']
                   for page in db.get(Document, document_id).extracted_text)
    before = len(state['calls'])
    peer_headers = {'Authorization': f"Bearer {create_access_token({'sub': '124'})}"}
    peer = client.get('/search', params={**params, 'owner_id': 123}, headers=peer_headers).json()
    assert peer['total_hits'] == 2
    assert {hit['document_id'] for hit in peer['hits']} == set(search_corpus['peer'])
    peer_texts = [item['content']['parts'][0]['text'] for batch in state['calls'][before:]
                  for item in batch if item['taskType'] == 'RETRIEVAL_DOCUMENT']
    assert Counter(peer_texts) == Counter(text for document_id in search_corpus['peer']
                                        for text in search_corpus['pages'][document_id] if text)
    with session_factory() as db:
        assert all(db.get(Document, document_id).extracted_text == pages
                   for document_id, pages in own_cache.items())


def test_semantic_http_filters_exclude_other_folders_labels_and_accounts_before_embedding(
        client, session_factory, search_corpus, corpus_embedding_api):
    """TC-US02-08: excluded sources must never be sent to the provider or cached."""
    state = corpus_embedding_api
    params = {'q': 'signed handover requirement', 'mode': 'semantic', 'limit': 100,
              'folder_id': search_corpus['folder_id'], 'label': ' contract '}
    response = client.get('/search', params=params)
    assert response.status_code == 200
    result = response.json()
    assert result['total_hits'] == 10
    assert {hit['document_id'] for hit in result['hits']} == set(search_corpus['filtered_hits'])
    expected = [text for document_id in search_corpus['filtered_candidates']
                for text in search_corpus['pages'][document_id] if text]
    assert Counter(embedded_texts(state, 'RETRIEVAL_DOCUMENT')) == Counter(expected)
    with session_factory() as db:
        for document in db.query(Document):
            assert any('search' in page for page in document.extracted_text) is (
                document.id in search_corpus['filtered_candidates'])
    calls = len(state['calls'])
    for override in ({'folder_id': search_corpus['peer_folder_id']}, {'folder_id': 99999},
                     {'label': '%'}, {'label': "' OR 1=1 --"}):
        empty = client.get('/search', params={**params, **override})
        assert empty.status_code == 200 and empty.json()['total_hits'] == 0 and empty.json()['hits'] == []
    assert len(state['calls']) == calls


@pytest.mark.parametrize('invalid_index', [0, 49], ids=['first-vector', 'last-vector-in-50'])
def test_bad_embedding_in_large_corpus_cannot_publish_a_partial_batch(
        client, session_factory, search_corpus, corpus_embedding_api, invalid_index):
    """TC-US02-09: validate the entire 50-passage batch before persisting any vector."""
    state = corpus_embedding_api
    state['invalid_index'] = invalid_index
    response = client.get('/search', params={'q': 'signed handover requirement', 'mode': 'semantic'})
    assert response.status_code == 503 and response.json()['detail']['code'] == 'embedding_unavailable'
    assert 'offline-us02-never-live' not in response.text
    assert len(state['calls']) == 1 and len(state['calls'][0]) == 50
    assert embedded_texts(state, 'RETRIEVAL_QUERY') == []
    with session_factory() as db:
        assert all('search' not in page for document in db.query(Document)
                   for page in document.extracted_text)
    # A provider failure must not break keyword retrieval of the saved source pages.
    content = client.get('/search', params={'q': 'Amber escrow release', 'limit': 100}).json()
    assert content['total_hits'] == 21
    assert {hit['document_id'] for hit in content['hits']} == set(search_corpus['relevant'])


def test_new_document_after_semantic_pagination_embeds_only_new_source_pages(
        client, search_corpus, add_document, corpus_embedding_api):
    """TC-US02-10: a cached 25-document account can grow and find the new source."""
    state = corpus_embedding_api
    params = {'q': 'signed handover requirement', 'mode': 'semantic', 'limit': 100}
    before = client.get('/search', params=params).json()
    assert before['total_hits'] == 21
    clause = 'Amber escrow release requires signed delivery acceptance. New source.'
    pages = ['New public cover.', '', clause]
    added = add_document(pages, name='new-semantic-contract.pdf')
    after = client.get('/search', params=params).json()
    assert after['total_hits'] == len(after['hits']) == 22
    assert {hit['document_id'] for hit in after['hits']} == set(search_corpus['relevant']) | {added}
    hit = next(hit for hit in after['hits'] if hit['document_id'] == added)
    assert hit['page'] == 3 and hit['snippet'] == clause and hit['doc_name'] == 'new-semantic-contract.pdf'
    batches = [batch for batch in state['calls'] if batch[0]['taskType'] == 'RETRIEVAL_DOCUMENT']
    assert [len(batch) for batch in batches] == [50, 2]
    assert [item['content']['parts'][0]['text'] for item in batches[-1]] == [pages[0], pages[2]]


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
