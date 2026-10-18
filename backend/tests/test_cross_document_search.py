"""Cross-document relevance, optional filters and exact ranked source snippets."""
from datetime import datetime, timedelta

import pytest

from app.api.search import get_search_embedder
from app.core.security import create_access_token
from app.main import app
from app.models import Document, FileFormat, Folder
from app.services.reader_extraction import extract_document_for_reader
from test_pdf_extraction import make_pdf


@pytest.fixture
def add_document(session_factory, tmp_path):
    def add(text, *, owner=123, name=None, label=None, user_label=None, folder=None):
        with session_factory() as db:
            number = db.query(Document).count()
            source = make_pdf(tmp_path / f'search-{number}.pdf', [
                f'BT /F1 12 Tf 30 720 Td ({text}) Tj ET'.encode('ascii')])
            document = Document(owner_id=owner, original_filename=name or f'search-{number}.pdf',
                                storage_path=str(source), file_format=FileFormat.PDF,
                                file_size_bytes=source.stat().st_size, ai_label=label,
                                user_label=user_label, folder_id=folder,
                                created_at=datetime.utcnow() - timedelta(days=1, seconds=100 - number),
                                expires_at=datetime.utcnow() + timedelta(days=30))
            db.add(document)
            db.commit()
            document_id = document.id
        extract_document_for_reader(document_id, session_factory)
        return document_id
    return add


def test_ranked_search_scans_beyond_visible_document_page(client, add_document):
    scattered = add_document('Payment follows delivery. The late shipment carries a penalty.')
    concise = add_document('Late payment penalty 0.05% per day. Value 1,200,000,000 VND.')
    for _ in range(22):
        add_document('Quarterly weather observations.')
    add_document('Payment instructions for a grocery order.')  # Partial overlap is insufficient.
    add_document('Weather observations.', name='late payment penalty.pdf')  # Filename is not evidence.

    visible = client.get('/documents', params={'limit': 5}).json()
    assert len(visible) == 5
    assert concise not in {document['id'] for document in visible}
    response = client.get('/search', params={'q': 'late payment penalty', 'limit': 1})
    assert response.status_code == 200
    result = response.json()
    assert result['total_hits'] == 2
    assert result['hits'][0]['document_id'] == concise
    assert '0.05% per day' in result['hits'][0]['snippet']
    assert '1,200,000,000 VND' in result['hits'][0]['snippet']
    second = client.get('/search', params={'q': 'late payment penalty', 'limit': 1, 'offset': 1}).json()
    assert second['total_hits'] == 2 and second['hits'][0]['document_id'] == scattered
    assert client.get('/search?q=astronomy').json()['total_hits'] == 0
    assert client.get('/search?q=payment%20astronomy').json()['hits'] == []
    assert client.get('/search?q=penalty&offset=100').json()['hits'] == []


def test_compact_snippet_opens_the_exact_matching_source_span(client, add_document, session_factory):
    document_id = add_document('Background information. ' * 24 + 'Late payment penalty 0.05% per day.')
    hit = client.get('/search?q=late%20payment%20penalty').json()['hits'][0]
    assert hit['document_id'] == document_id and hit['page'] == 1
    assert hit['start'] > 0 and len(hit['snippet']) <= 360
    assert 'Late payment penalty 0.05% per day.' in hit['snippet']
    page = client.get(f'/documents/{document_id}/pages').json()['pages'][0]
    assert page['text'][hit['start']:hit['end']] == hit['snippet']
    assert hit['highlight_url'] == f"/documents/{document_id}?page=1&start={hit['start']}&end={hit['end']}"
    with session_factory() as db:
        assert hit['reader_version'] == db.get(Document, document_id).extracted_text[0]['reader']['sha256']


def test_folder_and_effective_label_filters_are_combined_before_pagination(client, add_document, session_factory):
    with session_factory() as db:
        own = Folder(owner_id=123, name='Contracts')
        peer = Folder(owner_id=124, name='Private')
        db.add_all([own, peer])
        db.commit()
        own_id, peer_id = own.id, peer.id
    first = add_document('Payment penalty terms.', folder=own_id, label='Contract')
    corrected = add_document('Payment penalty terms.', folder=own_id, label='Report', user_label='Contract')
    add_document('Payment penalty terms.', folder=own_id, label='Contract', user_label='Report')
    add_document('Payment penalty terms.', label='Contract')
    add_document('Private payment penalty terms.', owner=124, folder=peer_id, label='Contract')
    params = {'q': 'payment penalty', 'folder_id': own_id, 'label': ' contract ', 'limit': 1}
    result = client.get('/search', params=params).json()
    assert result['total_hits'] == 2 and result['hits'][0]['document_id'] == first
    params['offset'] = 1
    assert client.get('/search', params=params).json()['hits'][0]['document_id'] == corrected
    assert client.get('/search', params={'q': 'payment', 'folder_id': peer_id}).json()['hits'] == []
    assert client.get('/search', params={'q': 'payment', 'folder_id': 99999}).json()['hits'] == []
    assert client.get('/search', params={'q': 'payment', 'label': '%'}).json()['hits'] == []
    assert client.get('/search', params={'q': 'payment', 'label': "' OR 1=1 --"}).json()['hits'] == []
    peer_headers = {'Authorization': f"Bearer {create_access_token({'sub': '124'})}"}
    assert client.get('/search', params={'q': 'payment', 'folder_id': own_id}, headers=peer_headers).json()['hits'] == []
    assert client.get('/search?q=private&owner_id=124').json()['total_hits'] == 0


@pytest.mark.parametrize('params', [
    {}, {'q': ''}, {'q': ' \t\n'}, {'q': 'x' * 501}, {'q': '%_!!!'}, {'q': '\U0001f642'},
    {'q': 'payment', 'folder_id': 0}, {'q': 'payment', 'folder_id': -1},
    {'q': 'payment', 'folder_id': 'invalid'}, {'q': 'payment', 'label': ''},
    {'q': 'payment', 'label': '   '}, {'q': 'payment', 'label': 'x' * 101},
])
def test_invalid_queries_and_filters_return_validation_errors(client, params):
    assert client.get('/search', params=params).status_code == 422


def test_semantic_search_rejects_weak_neighbors_and_embeds_only_filtered_authorized_sources(client, add_document):
    relevant = add_document('Background information. ' * 24 + 'Relevant late payment provision.', label='Contract')
    add_document('Weak weather forecast.', label='Contract')
    add_document('Excluded medical notes.', label='Report')
    add_document('Private financial records.', owner=124, label='Contract')

    class Embedder:
        model_key = 'ranked-search-test:2'
        seen = []

        def embed(self, texts, *, task):
            if task == 'RETRIEVAL_QUERY':
                return [[1., 0.]]
            self.seen.extend(texts)
            return [[0.8, 0.6] if 'Relevant' in text else [0.4, 0.916515139]
                    for text in texts]

    embedder = Embedder()
    app.dependency_overrides[get_search_embedder] = lambda: embedder
    try:
        result = client.get('/search', params={'q': 'fees for tardiness', 'mode': 'semantic', 'label': 'Contract'}).json()
        assert result['total_hits'] == 1 and result['hits'][0]['document_id'] == relevant
        assert 'Relevant late payment provision.' in result['hits'][0]['snippet']
        assert all('Excluded' not in text and 'Private' not in text for text in embedder.seen)
        assert client.get('/search', params={'q': 'fees', 'mode': 'semantic', 'label': 'Unknown'}).json()['hits'] == []
    finally:
        app.dependency_overrides.pop(get_search_embedder, None)


def test_cross_language_semantic_scores_below_old_cutoff_keep_only_the_closest_band(client, add_document):
    relevant = add_document('Education and teaching students at school.')
    add_document('Weather and sea observations.')
    class Embedder:
        model_key = 'cross-language-test:2'
        def embed(self, texts, *, task):
            if task == 'RETRIEVAL_QUERY':
                return [[1., 0.]]
            scores = [0.6426 if 'Education' in text else 0.6139 for text in texts]
            return [[score, (1 - score * score) ** .5] for score in scores]
    app.dependency_overrides[get_search_embedder] = lambda: Embedder()
    try:
        result = client.get('/search', params={'q': 'giáo dục', 'mode': 'semantic'})
        assert result.status_code == 200
        assert [hit['document_id'] for hit in result.json()['hits']] == [relevant]
    finally:
        app.dependency_overrides.pop(get_search_embedder, None)
