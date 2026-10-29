"""20-document content/semantic retrieval with exact, owner-isolated source spans."""
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token
from app.db.database import Base
from app.main import app
from app.api.search import get_search_embedder
from app.models import Document, FileFormat, User
from app.schemas.search import search_hit_to_evidence, SearchHit
from app.services import search_index as index
from app.services.processing import process_job
from app.services.reader_extraction import extract_document_for_reader
from test_pdf_extraction import make_pdf
from test_cross_document_search import add_document, search_corpus


def test_large_corpus_hits_round_trip_to_exact_reader_pages_and_evidence(
        client, session_factory, search_corpus):
    """TC-US02-05: every matching span belongs to its physical page and reader version."""
    response = client.get('/search', params={'q': 'Amber escrow release', 'limit': 100})
    assert response.status_code == 200
    hits = response.json()['hits']
    assert len(hits) == 21
    with session_factory() as db:
        assert db.query(Document).filter_by(owner_id=123).count() == 25
        assert db.query(Document).filter_by(owner_id=124).count() == 2
        for raw in hits:
            hit = SearchHit.model_validate(raw)
            document = db.get(Document, hit.document_id)
            assert hit.doc_name == search_corpus['names'][document.id] == document.original_filename
            assert hit.page == 3 and document.page_count == 3
            assert document.extracted_text[1]['text'] == ''
            page = document.extracted_text[hit.page - 1]
            assert page['text'][hit.start:hit.end] == hit.snippet == search_corpus['pages'][document.id][2]
            assert hit.reader_version == page['reader']['sha256']
            assert hit.highlight_url == (
                f'/documents/{document.id}?page=3&start={hit.start}&end={hit.end}')
            evidence = search_hit_to_evidence(hit)
            assert (evidence.document_id, evidence.page, evidence.start, evidence.end,
                    evidence.quote, evidence.reader_version) == (
                        document.id, 3, hit.start, hit.end, hit.snippet, hit.reader_version)
            opened = client.get(f'/documents/{document.id}/pages/3/text')
            assert opened.status_code == 200
            assert opened.json()['text'][hit.start:hit.end] == hit.snippet
        # Content searches do not create semantic caches or modify the source text.
        assert all('search' not in page for document in db.query(Document)
                   for page in document.extracted_text)


def test_new_document_is_searchable_beyond_the_initial_twenty_without_rebuilding_old_sources(
        client, session_factory, search_corpus, add_document):
    """TC-US02-06: growing the account must not truncate the corpus or stale the results."""
    params = {'q': 'Amber escrow release', 'limit': 100}
    before = client.get('/search', params=params).json()
    assert before['total_hits'] == 21
    with session_factory() as db:
        saved_pages = {document.id: deepcopy(document.extracted_text)
                       for document in db.query(Document)}
    clause = 'Amber escrow release requires signed delivery acceptance. Added after the first search.'
    added = add_document(['New contract cover.', '', 'Administrative annex.', clause], name='new-contract.pdf')
    after = client.get('/search', params=params).json()
    assert after['total_hits'] == len(after['hits']) == 22
    assert {hit['document_id'] for hit in after['hits']} == set(search_corpus['relevant']) | {added}
    hit = next(hit for hit in after['hits'] if hit['document_id'] == added)
    assert hit['doc_name'] == 'new-contract.pdf' and hit['page'] == 4 and hit['snippet'] == clause
    last_page = client.get('/search', params={**params, 'limit': 20, 'offset': 20}).json()
    assert last_page['total_hits'] == 22 and last_page['hits'] == after['hits'][20:]
    with session_factory() as db:
        assert db.query(Document).filter_by(owner_id=123).count() == 26
        for document_id, pages in saved_pages.items():
            assert db.get(Document, document_id).extracted_text == pages


@pytest.fixture
def corpus(session_factory, tmp_path):
    ids = []
    for number in range(21):
        owner = 123 if number < 20 else 124
        lines = [f'Owner {owner} report {number}.', '',
                 ('Peer private secret. ' if owner == 124 else '') + 'Late payment penalty 0.05% per day. Value 1,200,000,000 VND.']
        source = make_pdf(tmp_path / f'source-{number}.pdf', [
            f'BT /F1 12 Tf 30 720 Td ({line}) Tj ET'.encode() if line else b'' for line in lines
        ])
        with session_factory() as db:
            document = Document(owner_id=owner, original_filename=f'contract-{number}.pdf',
                                storage_path=str(source), file_format=FileFormat.PDF,
                                file_size_bytes=source.stat().st_size, expires_at=datetime.utcnow() + timedelta(days=30))
            db.add(document)
            db.commit()
            ids.append(document.id)
        extract_document_for_reader(ids[-1], session_factory)
    return ids


def test_twenty_documents_have_page_metadata_exact_passages_and_equivalent_evidence(client, session_factory, corpus):
    response = client.get('/search', params={'q': 'late payment', 'limit': 100})
    assert response.status_code == 200
    saved = response.json()
    assert saved['total_hits'] == len(saved['hits']) == 20
    assert {hit['document_id'] for hit in saved['hits']} == set(corpus[:20])
    with session_factory() as db:
        assert db.query(Document).filter_by(owner_id=123).count() == 20
        for hit in saved['hits']:
            document = db.get(Document, hit['document_id'])
            assert hit['doc_name'] == document.original_filename and hit['page'] == 3
            assert document.extracted_text[2]['text'][hit['start']:hit['end']] == hit['snippet']
            assert '0.05% per day' in hit['snippet'] and '1,200,000,000 VND' in hit['snippet']
            assert hit['reader_version'] == document.extracted_text[2]['reader']['sha256']
            evidence = search_hit_to_evidence(SearchHit.model_validate(hit))
            assert evidence.quote == hit['snippet'] and evidence.document_id == document.id
            assert hit['highlight_url'] == f"/documents/{document.id}?page=3&start={hit['start']}&end={hit['end']}"
    next_page = client.get('/search', params={'q': 'late payment', 'limit': 5, 'offset': 5}).json()
    assert next_page['total_hits'] == 20 and next_page['hits'] == saved['hits'][5:10]


def test_search_owner_is_always_taken_from_authentication(client, corpus):
    peer = {'Authorization': f"Bearer {create_access_token({'sub': '124'})}"}
    assert {hit['document_id'] for hit in client.get('/search?q=penalty', headers=peer).json()['hits']} == {corpus[-1]}
    assert client.get('/search?q=private&owner_id=124').json()['hits'] == []
    assert client.get('/search?q=penalty', headers={'Authorization': 'Bearer invalid', 'Cookie': ''}).status_code == 401
    for params in [{'q': ' '}, {'q': 'penalty', 'limit': 0}, {'q': 'penalty', 'offset': -1}, {'q': 'penalty', 'mode': 'unsupported'}]:
        assert client.get('/search', params=params).status_code == 422
    assert client.get('/search?q=%25').status_code == 422


def test_unicode_chunks_cover_original_text_and_normalization_never_changes_offsets():
    text = ('Điều khoản 🙂 e\u0301 thanh toán 1,200,000,000 VND.\n' * 100) + 'End'
    chunks = list(index.passages(text))
    covered = set()
    for start, end, snippet in chunks:
        assert text[start:end] == snippet and 0 < end - start <= index.CHUNK_SIZE
        covered.update(range(start, end))
    assert covered == set(range(len(text)))
    assert index.tokens('ĐIỀU KHOẢN thanh toán') == index.tokens('dieu khoan thanh toan')
    assert len(index.tokens('a' * 100)[0]) == 64


def test_index_schema_compiles_for_the_existing_mysql_stack():
    from sqlalchemy.dialects.mysql import dialect
    from sqlalchemy.schema import CreateIndex, CreateTable
    assert set(Base.metadata.tables) == {'users', 'folders', 'documents', 'jobs', 'job_files', 'citations'}
    for table in Base.metadata.sorted_tables:
        assert 'CREATE TABLE' in str(CreateTable(table).compile(dialect=dialect()))
        for table_index in table.indexes:
            assert 'INDEX' in str(CreateIndex(table_index).compile(dialect=dialect()))


@pytest.mark.parametrize('mutation', [
    lambda doc: setattr(doc, 'page_count', 99),
    lambda doc: doc.extracted_text[0].update(page=True),
    lambda doc: doc.extracted_text[0].update(reader={}),
])
def test_invalid_page_metadata_cannot_publish_search_references(session_factory, corpus, mutation):
    with session_factory() as db:
        document = db.get(Document, corpus[0])
        document.extracted_text = deepcopy(document.extracted_text)
        mutation(document)
        assert index.document_passages(document) == []
        db.rollback()


def test_source_byte_changes_remove_stale_index_then_reextraction_replaces_it(client, session_factory, corpus):
    document_id = corpus[0]
    with session_factory() as db:
        source = Path(db.get(Document, document_id).storage_path)
        old_version = db.get(Document, document_id).extracted_text[0]['reader']['sha256']
    make_pdf(source, [b'BT /F1 12 Tf 30 720 Td (Revised amount 950 EUR.) Tj ET'])
    hits = client.get('/search?q=penalty&limit=100').json()['hits']
    assert len(hits) == 19 and document_id not in {hit['document_id'] for hit in hits}
    extract_document_for_reader(document_id, session_factory)
    hit = client.get('/search?q=revised').json()['hits'][0]
    assert hit['document_id'] == document_id and hit['page'] == 1 and '950 EUR' in hit['snippet']
    assert hit['reader_version'] != old_version
    with session_factory() as db:
        before = deepcopy(db.get(Document, document_id).extracted_text)
    extract_document_for_reader(document_id, session_factory)
    with session_factory() as db:
        assert db.get(Document, document_id).extracted_text == before


def test_rename_expiry_delete_and_missing_sources_remove_index_entries(client, session_factory, corpus):
    with session_factory() as db:
        db.get(Document, corpus[0]).original_filename = 'renamed.pdf'
        db.get(Document, corpus[1]).expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.delete(db.get(Document, corpus[2]))
        Path(db.get(Document, corpus[3]).storage_path).unlink()
        db.commit()
    hits = client.get('/search?q=penalty&limit=100').json()['hits']
    assert len(hits) == 17
    assert next(hit for hit in hits if hit['document_id'] == corpus[0])['doc_name'] == 'renamed.pdf'
    peer = {'Authorization': f"Bearer {create_access_token({'sub': '124'})}"}
    assert len(client.get('/search?q=penalty', headers=peer).json()['hits']) == 1


def test_index_and_content_replacement_roll_back_together(session_factory, corpus):
    with session_factory() as db:
        document = db.get(Document, corpus[0])
        before = deepcopy(document.extracted_text)
        pages = deepcopy(before)
        pages[2]['text'] = 'Replacement content.'
        document.extracted_text = pages
        db.rollback()
        assert db.get(Document, corpus[0]).extracted_text == before
        assert any('penalty' in passage.text for passage, _, _ in index.document_passages(document))


class SemanticEmbedder:
    model_key = 'offline-semantic-test:3'

    def __init__(self):
        self.calls = []

    def embed(self, texts, *, task):
        self.calls.append((list(texts), task))
        return [[1., 0., 0.] if 'penalty' in text or task == 'RETRIEVAL_QUERY' else [0., 1., 0.] for text in texts]


def test_semantic_vectors_are_persisted_reused_and_never_embed_other_owners_content(client, session_factory, corpus):
    embedder = SemanticEmbedder()
    app.dependency_overrides[get_search_embedder] = lambda: embedder
    try:
        assert client.get('/search?q=fees%20for%20tardiness').json()['hits'] == []
        hits = client.get('/search', params={'q': 'fees for tardiness', 'mode': 'semantic', 'limit': 100}).json()['hits']
        assert len(hits) == 20 and all(hit['page'] == 3 for hit in hits)
        assert not any('Peer private' in text for texts, _ in embedder.calls for text in texts)
        document_calls = sum(task == 'RETRIEVAL_DOCUMENT' for _, task in embedder.calls)
        assert document_calls == 1
        assert client.get('/search?q=fees&mode=semantic').status_code == 200
        assert sum(task == 'RETRIEVAL_DOCUMENT' for _, task in embedder.calls) == document_calls
        reader_pages = client.get(f'/documents/{corpus[0]}/pages').json()['pages']
        assert all('search' not in page for page in reader_pages)
        with session_factory() as db:
            for document in db.query(Document).filter_by(owner_id=123):
                assert all(page['search']['model'] == embedder.model_key for page in document.extracted_text if page['text'])
            assert all('search' not in page for page in db.get(Document, corpus[-1]).extracted_text)
        embedder.model_key = 'offline-new-model:3'
        assert client.get('/search?q=fees&mode=semantic').status_code == 200
        assert sum(task == 'RETRIEVAL_DOCUMENT' for _, task in embedder.calls) == 2
    finally:
        app.dependency_overrides.pop(get_search_embedder, None)


def test_failed_embeddings_do_not_publish_partial_vectors_and_content_search_keeps_working(client, session_factory, corpus):
    class Broken(SemanticEmbedder):
        def embed(self, texts, *, task):
            return [[float('nan')]] * len(texts)
    app.dependency_overrides[get_search_embedder] = lambda: Broken()
    try:
        assert client.get('/search?q=fees&mode=semantic').status_code == 503
    finally:
        app.dependency_overrides.pop(get_search_embedder, None)
    with session_factory() as db:
        assert all('search' not in page for doc in db.query(Document) for page in doc.extracted_text)
    assert client.get('/search?q=penalty').json()['total_hits'] == 20
    assert client.get('/search?q=fees&mode=semantic').status_code == 503  # No live key in tests.


def test_upload_job_indexes_saved_pages_without_additional_model_calls(client, session_factory, tmp_path):
    source = make_pdf(tmp_path / 'upload.pdf', [b'BT /F1 12 Tf 30 720 Td (Indexed upload text.) Tj ET'])
    uploaded = client.post('/upload', files=[('files', ('upload.pdf', source.read_bytes(), 'application/pdf'))])
    process_job(int(uploaded.json()['jobId']), session_factory)
    hit = client.get('/search?q=indexed').json()['hits'][0]
    assert hit['doc_name'] == 'upload.pdf' and hit['snippet'] == 'Indexed upload text.'


def test_invalid_query_embedding_does_not_save_partial_json_cache(client, session_factory, corpus):
    class BrokenQuery(SemanticEmbedder):
        def embed(self, texts, *, task):
            return [[0., 0., 0.]] if task == 'RETRIEVAL_QUERY' else super().embed(texts, task=task)
    app.dependency_overrides[get_search_embedder] = lambda: BrokenQuery()
    try:
        assert client.get('/search?q=fees&mode=semantic').status_code == 503
        with session_factory() as db:
            assert all('search' not in page for doc in db.query(Document) for page in doc.extracted_text)
    finally:
        app.dependency_overrides.pop(get_search_embedder, None)


def test_changed_source_replaces_saved_semantic_cache(client, session_factory, corpus):
    embedder = SemanticEmbedder()
    app.dependency_overrides[get_search_embedder] = lambda: embedder
    try:
        assert client.get('/search?q=fees&mode=semantic').status_code == 200
        with session_factory() as db:
            document = db.get(Document, corpus[0])
            old_revision = document.extracted_text[2]['search']['revision']
            source = Path(document.storage_path)
        make_pdf(source, [b'BT /F1 12 Tf 30 720 Td (Revised penalty 950 EUR.) Tj ET'])
        assert client.get('/search?q=fees&mode=semantic').json()['total_hits'] == 19
        extract_document_for_reader(corpus[0], session_factory)
        assert client.get('/search?q=fees&mode=semantic').json()['total_hits'] == 20
        assert sum(task == 'RETRIEVAL_DOCUMENT' for _, task in embedder.calls) == 2
        with session_factory() as db:
            assert db.get(Document, corpus[0]).extracted_text[0]['search']['revision'] != old_revision
    finally:
        app.dependency_overrides.pop(get_search_embedder, None)


def test_saved_pages_are_searchable_after_restart_with_only_design_tables(session_factory, corpus):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    try:
        with session_factory() as source_db, factory() as db:
            source = source_db.get(Document, corpus[0])
            db.add(User(id=123, username='legacy', email='legacy@example.com', password_hash='unused'))
            db.add(Document(id=source.id, owner_id=123, original_filename=source.original_filename,
                            storage_path=source.storage_path, file_format=source.file_format,
                            file_size_bytes=source.file_size_bytes, page_count=source.page_count,
                            extracted_text=source.extracted_text, expires_at=source.expires_at))
            db.commit()
        with factory() as db:
            result = index.search_passages(db, 123, 'late payment')
            assert result.total_hits == 1 and result.hits[0].page == 3
    finally:
        engine.dispose()


def test_quota_keeps_completed_batches_and_retry_only_embeds_remaining_sources(client, session_factory, corpus, monkeypatch):
    from app.services.search_embeddings import EmbeddingUnavailable
    monkeypatch.setattr(index, 'CHUNK_SIZE', 40)
    monkeypatch.setattr(index, 'CHUNK_OVERLAP', 10)

    class Limited(SemanticEmbedder):
        document_calls = 0
        def embed(self, texts, *, task):
            if task == 'RETRIEVAL_DOCUMENT':
                self.document_calls += 1
                if self.document_calls == 2:
                    raise EmbeddingUnavailable(code='embedding_rate_limited', retry_after=12)
            return super().embed(texts, task=task)

    embedder = Limited()
    app.dependency_overrides[get_search_embedder] = lambda: embedder
    try:
        response = client.get('/search?q=fees&mode=semantic')
        assert response.status_code == 503
        assert response.headers['Retry-After'] == '12'
        assert response.json()['detail']['code'] == 'embedding_rate_limited'
        assert '12 giây' in response.json()['detail']['message']
        with session_factory() as db:
            saved = sum(len(page.get('search', {}).get('passages', {}))
                        for doc in db.query(Document).filter_by(owner_id=123) for page in doc.extracted_text)
            assert saved == 50
            assert all('search' not in page for page in db.get(Document, corpus[-1]).extracted_text)
        assert client.get('/search?q=fees&mode=semantic').status_code == 200
        # No text from the completed first batch is sent again on retry.
        texts = [text for batch, task in embedder.calls if task == 'RETRIEVAL_DOCUMENT' for text in batch]
        with session_factory() as db:
            total = sum(len(index.document_passages(doc)) for doc in db.query(Document).filter_by(owner_id=123))
        assert len(texts) == total
    finally:
        app.dependency_overrides.pop(get_search_embedder, None)
