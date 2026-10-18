"""20-document content/semantic retrieval with exact, owner-isolated source spans."""
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token
from app.db.database import Base
from app.main import app
from app.api.search import get_search_embedder
from app.models import Document, FileFormat, SearchDocument, SearchPassage, SearchTerm, User
from app.schemas.search import search_hit_to_evidence, SearchHit
from app.services import search_index as index
from app.services.processing import process_job
from app.services.reader_extraction import extract_document_for_reader
from test_pdf_extraction import make_pdf


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
        assert db.query(SearchDocument).filter_by(owner_id=123).count() == 20
        assert db.query(SearchPassage).filter_by(owner_id=123).count() == 40
        assert db.query(SearchTerm).filter_by(owner_id=123).count() > 40
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
    assert client.get('/search?q=%25').json()['hits'] == []


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
    for model in (SearchDocument, SearchPassage, SearchTerm):
        assert 'CREATE TABLE' in str(CreateTable(model.__table__).compile(dialect=dialect()))
        for table_index in model.__table__.indexes:
            assert 'CREATE INDEX' in str(CreateIndex(table_index).compile(dialect=dialect()))


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
        assert index.sync_document_index(db, document) == 0
        assert db.get(SearchDocument, document.id) is None
        db.rollback()


def test_source_byte_changes_remove_stale_index_then_reextraction_replaces_it(client, session_factory, corpus):
    document_id = corpus[0]
    with session_factory() as db:
        source = Path(db.get(Document, document_id).storage_path)
        old_version = db.get(SearchDocument, document_id).reader_version
    make_pdf(source, [b'BT /F1 12 Tf 30 720 Td (Revised amount 950 EUR.) Tj ET'])
    hits = client.get('/search?q=penalty&limit=100').json()['hits']
    assert len(hits) == 19 and document_id not in {hit['document_id'] for hit in hits}
    with session_factory() as db:
        assert db.get(SearchDocument, document_id) is None
        assert db.query(SearchPassage).filter_by(document_id=document_id).count() == 0
    extract_document_for_reader(document_id, session_factory)
    hit = client.get('/search?q=revised').json()['hits'][0]
    assert hit['document_id'] == document_id and hit['page'] == 1 and '950 EUR' in hit['snippet']
    assert hit['reader_version'] != old_version
    with session_factory() as db:
        before = [(passage.id, passage.text) for passage in db.get(SearchDocument, document_id).passages]
    extract_document_for_reader(document_id, session_factory)
    with session_factory() as db:
        assert [(passage.id, passage.text) for passage in db.get(SearchDocument, document_id).passages] == before


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
    with session_factory() as db:
        for document_id in corpus[1:4]:
            assert db.get(SearchDocument, document_id) is None
            assert db.query(SearchPassage).filter_by(document_id=document_id).count() == 0
        assert db.get(SearchDocument, corpus[-1]) is not None  # Cleanup respects the requesting owner.


def test_index_and_content_replacement_roll_back_together(session_factory, corpus):
    with session_factory() as db:
        document = db.get(Document, corpus[0])
        before = deepcopy(document.extracted_text)
        revision = db.get(SearchDocument, document.id).revision
        pages = deepcopy(before)
        pages[2]['text'] = 'Replacement content.'
        document.extracted_text = pages
        index.sync_document_index(db, document)
        db.rollback()
        assert db.get(Document, corpus[0]).extracted_text == before
        assert db.get(SearchDocument, corpus[0]).revision == revision
        assert any('penalty' in passage.text for passage in db.get(SearchDocument, corpus[0]).passages)


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
        with session_factory() as db:
            assert all(passage.embedding_model == embedder.model_key for passage in db.query(SearchPassage).filter_by(owner_id=123))
            assert all(passage.embedding is None for passage in db.query(SearchPassage).filter_by(owner_id=124))
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
        assert db.query(SearchPassage).filter(SearchPassage.embedding.is_not(None)).count() == 0
    assert client.get('/search?q=penalty').json()['total_hits'] == 20
    assert client.get('/search?q=fees&mode=semantic').status_code == 503  # No live key in tests.


def test_upload_job_indexes_saved_pages_without_additional_model_calls(client, session_factory, tmp_path):
    source = make_pdf(tmp_path / 'upload.pdf', [b'BT /F1 12 Tf 30 720 Td (Indexed upload text.) Tj ET'])
    uploaded = client.post('/upload', files=[('files', ('upload.pdf', source.read_bytes(), 'application/pdf'))])
    process_job(int(uploaded.json()['jobId']), session_factory)
    hit = client.get('/search?q=indexed').json()['hits'][0]
    assert hit['doc_name'] == 'upload.pdf' and hit['snippet'] == 'Indexed upload text.'


def test_additive_migration_backfills_legacy_documents_idempotently(session_factory, corpus):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
    from init_search_index import initialize_search_index
    engine = create_engine('sqlite://')
    tables = [table for table in Base.metadata.sorted_tables if not table.name.startswith('search_')]
    Base.metadata.create_all(engine, tables=tables)
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
        assert initialize_search_index(engine, factory) == 1
        assert initialize_search_index(engine, factory) == 1
        with factory() as db:
            assert db.query(SearchDocument).count() == 1 and db.query(SearchPassage).count() == 2
    finally:
        engine.dispose()
