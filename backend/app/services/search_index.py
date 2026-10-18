"""Exact source spans plus an owner-scoped inverted index and reusable vectors.

No DB-specific full-text/vector extension is required for a 20-document account.
Embeddings are optional and computed lazily by semantic search, outside US07 jobs.
The caller owns the transaction; failed indexing rolls back with extraction.
"""
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata

from sqlalchemy import func

from app.models import Document, SearchDocument, SearchPassage, SearchTerm
from app.schemas.search import SearchHit, SearchResponse

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
SNIPPET_SIZE = 360
# A positive cosine alone also admits weak, unrelated neighbors. This conservative
# cutoff permits an empty response rather than forcing a nearest-neighbor match.
MIN_SEMANTIC_SCORE = 0.65


def fold(text):
    return ''.join(char for char in unicodedata.normalize('NFKD', text.casefold())
                   if not unicodedata.combining(char)).replace('đ', 'd')


def tokens(text):
    return [word if len(word) <= 64 else '#' + hashlib.sha256(word.encode()).hexdigest()[:63]
            for word in re.findall(r'[^\W_]+', fold(text))]


def passages(text):
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            boundary = max(text.rfind('\n', start + CHUNK_SIZE // 2, end),
                           text.rfind(' ', start + CHUNK_SIZE // 2, end))
            if boundary > start:
                end = boundary
        if text[start:end].strip():
            yield start, end, text[start:end]
        if end == len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)


def index_payload(document):
    pages = document.extracted_text
    if not isinstance(pages, list) or not pages or document.page_count != len(pages):
        return None
    values = []
    for number, page in enumerate(pages, 1):
        if (not isinstance(page, dict) or type(page.get('page')) is not int or
                page['page'] != number or not isinstance(page.get('text'), str)):
            return None
        reference = page.get('reader', {})
        if not isinstance(reference, dict) or any(not re.fullmatch(r'[0-9a-f]{64}', str(reference.get(key, '')))
                                                  for key in ('sha256', 'source_sha256')):
            return None
        values.append([number, page['text'], reference['sha256'], reference['source_sha256']])
    if any(value[2:] != values[0][2:] for value in values):
        return None
    revision = hashlib.sha256(json.dumps([document.owner_id, document.original_filename, values],
                                        ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    return revision, values[0][2], values[0][3]


def remove_document_index(db, document_id):
    snapshot = db.get(SearchDocument, document_id)
    if snapshot is not None:
        db.delete(snapshot)
        db.flush()


def sync_document_index(db, document, *, now=None):
    now = now or datetime.utcnow()
    payload = index_payload(document)
    if document.expires_at is None or document.expires_at <= now or payload is None:
        remove_document_index(db, document.id)
        return 0
    revision, reader_version, source_hash = payload
    snapshot = db.get(SearchDocument, document.id)
    if snapshot is not None and snapshot.revision == revision:
        return len(snapshot.passages)
    if snapshot is None:
        snapshot = SearchDocument(document_id=document.id)
        db.add(snapshot)
    else:
        snapshot.passages.clear()
        db.flush()
    snapshot.owner_id = document.owner_id
    snapshot.doc_name = document.original_filename
    snapshot.revision = revision
    snapshot.reader_version = reader_version
    snapshot.source_sha256 = source_hash
    for page in document.extracted_text:
        for start, end, text in passages(page['text']):
            passage = SearchPassage(document_id=document.id, owner_id=document.owner_id,
                                    page=page['page'], start=start, end=end, text=text)
            passage.terms = [SearchTerm(term=term, owner_id=document.owner_id, frequency=count)
                             for term, count in Counter(tokens(text)).items()]
            snapshot.passages.append(passage)
    db.flush()
    return len(snapshot.passages)


def purge_expired_index(db, *, owner_id=None, now=None):
    now = now or datetime.utcnow()
    query = db.query(SearchDocument).outerjoin(Document, Document.id == SearchDocument.document_id)
    if owner_id is not None:
        query = query.filter(SearchDocument.owner_id == owner_id)
    stale = query.filter((Document.id.is_(None)) | (Document.expires_at <= now) |
                         (Document.owner_id != SearchDocument.owner_id)).all()
    for snapshot in stale:
        db.delete(snapshot)
    db.flush()
    return len(stale)


def reconcile_owner_index(db, owner_id, *, now=None):
    """Backfill legacy extractions and remove stale bytes, expired docs and renames."""
    from app.services.reader_extraction import ReaderConversionError, reader_representation, sha256
    now = now or datetime.utcnow()
    purge_expired_index(db, owner_id=owner_id, now=now)
    documents = db.query(Document).filter(Document.owner_id == owner_id, Document.expires_at > now).all()
    for document in documents:
        try:
            path, reference = reader_representation(document)
            if (not Path(document.storage_path).is_file() or
                    sha256(document.storage_path) != reference['source_sha256'] or sha256(path) != reference['sha256']):
                remove_document_index(db, document.id)
                continue
        except (ReaderConversionError, OSError):
            remove_document_index(db, document.id)
            continue
        sync_document_index(db, document, now=now)


def normalized_vector(vector):
    if not isinstance(vector, list) or not vector or any(type(value) not in (int, float) or not math.isfinite(value) for value in vector):
        raise ValueError('Invalid search embedding.')
    norm = math.sqrt(sum(value * value for value in vector))
    if not math.isfinite(norm) or not norm:
        raise ValueError('Invalid search embedding.')
    return [value / norm for value in vector]


def ranked_excerpt(passage, terms):
    """Choose an exact, compact source span around the most query terms."""
    if len(passage.text) <= SNIPPET_SIZE:
        return passage.start, passage.end, passage.text
    matches = [(match.start(), match.end(), tokens(match.group())[0])
               for match in re.finditer(r'[^\W_]+', passage.text)
               if tokens(match.group())[0] in terms]
    windows = []
    for begin, end, _ in matches:
        left = max(0, min(begin - 60, len(passage.text) - SNIPPET_SIZE))
        right = max(left + SNIPPET_SIZE, end)
        coverage = len({term for start, finish, term in matches if start >= left and finish <= right})
        windows.append((coverage, -left, left, right))
    if windows:
        _, _, left, right = max(windows)
    else:
        # Semantic paraphrases may have no shared words. Keep the indexed
        # passage intact instead of arbitrarily cutting away its relevant tail.
        return passage.start, passage.end, passage.text
    return passage.start + left, passage.start + right, passage.text[left:right]


def search_passages(db, owner_id, query, *, mode='content', limit=20, offset=0, embedder=None,
                    folder_id=None, label=None, now=None):
    now = now or datetime.utcnow()
    if mode not in ('content', 'semantic'):
        raise ValueError('Unsupported search mode.')
    if mode == 'semantic' and embedder is None:
        raise ValueError('Semantic search requires an embedding provider.')
    reconcile_owner_index(db, owner_id, now=now)
    candidates = db.query(SearchPassage, SearchDocument, Document).join(
        SearchDocument, SearchDocument.document_id == SearchPassage.document_id).join(
        Document, Document.id == SearchPassage.document_id).filter(
        SearchPassage.owner_id == owner_id, SearchDocument.owner_id == owner_id,
        Document.owner_id == owner_id, Document.expires_at > now)
    if folder_id is not None:
        candidates = candidates.filter(Document.folder_id == folder_id)
    if label is not None:
        # A manual correction supersedes the predicted label. Equality avoids
        # treating wildcard characters supplied by the user as a broad match.
        effective_label = func.coalesce(func.nullif(func.trim(Document.user_label), ''), Document.ai_label)
        candidates = candidates.filter(func.lower(effective_label) == label.lower())
    terms = set(tokens(query))
    if mode == 'content':
        if not terms:
            return SearchResponse(query=query, total_hits=0)
        candidates = candidates.join(SearchTerm, SearchTerm.passage_id == SearchPassage.id).filter(
            SearchTerm.owner_id == owner_id, SearchTerm.term.in_(terms)).distinct()
    rows = candidates.all()
    scored = []
    if mode == 'semantic' and rows:
        missing = [passage for passage, _, _ in rows if passage.embedding_model != embedder.model_key or passage.embedding is None]
        if missing:
            vectors = embedder.embed([passage.text for passage in missing], task='RETRIEVAL_DOCUMENT')
            if len(vectors) != len(missing):
                raise ValueError('Embedding count does not match indexed passages.')
            validated = [normalized_vector(vector) for vector in vectors]
            for passage, vector in zip(missing, validated):
                passage.embedding = vector
                passage.embedding_model = embedder.model_key
        vector = normalized_vector(embedder.embed([query], task='RETRIEVAL_QUERY')[0])
        for passage, snapshot, document in rows:
            stored = normalized_vector(passage.embedding)
            if len(stored) != len(vector):
                raise ValueError('Search embedding dimensions differ.')
            score = sum(left * right for left, right in zip(vector, stored))
            if score >= MIN_SEMANTIC_SCORE:
                scored.append((score, passage, snapshot, document))
    elif mode == 'content':
        frequencies = [Counter(tokens(passage.text)) for passage, _, _ in rows]
        average_length = sum(sum(found.values()) for found in frequencies) / max(len(rows), 1)
        document_frequency = Counter(term for found in frequencies for term in terms.intersection(found))
        for (passage, snapshot, document), found in zip(rows, frequencies):
            # Do not present a partial keyword overlap as a matching fact.
            if not terms.issubset(found):
                continue
            length_ratio = sum(found.values()) / average_length
            score = sum(math.log(1 + (len(rows) - document_frequency[term] + 0.5) /
                                 (document_frequency[term] + 0.5)) *
                        (found[term] * 2.2) / (found[term] + 1.2 * (0.25 + 0.75 * length_ratio))
                        for term in terms)
            score += 1 if fold(query) in fold(passage.text) else 0
            scored.append((score, passage, snapshot, document))
    scored.sort(key=lambda row: (-row[0], row[1].document_id, row[1].page, row[1].start))
    hits = []
    for score, passage, snapshot, document in scored[offset:offset + limit]:
        start, end, snippet = ranked_excerpt(passage, terms)
        hits.append(SearchHit(
            document_id=passage.document_id, doc_name=snapshot.doc_name, page=passage.page,
            start=start, end=end, snippet=snippet, reader_version=snapshot.reader_version,
            highlight_url=f'/documents/{passage.document_id}?page={passage.page}&start={start}&end={end}',
            score=score, ai_label=document.ai_label, folder_id=document.folder_id))
    return SearchResponse(query=query, total_hits=len(scored), hits=hits)
