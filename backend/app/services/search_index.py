"""Search the six-table design using the existing documents.extracted_text JSON.

Passages and term frequencies are derived in memory from authorized saved pages.
Optional vectors are cached in those pages' JSON, never in additional tables.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata

from sqlalchemy import func

from app.models import Document
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


@dataclass
class IndexedPassage:
    document_id: int
    page: int
    start: int
    end: int
    text: str
    embedding: list | None = None


@dataclass(frozen=True)
class IndexedDocument:
    doc_name: str
    revision: str
    reader_version: str


def document_passages(document):
    payload = index_payload(document)
    if payload is None:
        return []
    revision, version, _ = payload
    snapshot = IndexedDocument(document.original_filename, revision, version)
    return [(IndexedPassage(document.id, page['page'], start, end, text), snapshot, document)
            for page in document.extracted_text for start, end, text in passages(page['text'])]


def authorized_passages(documents):
    """Reject changed/missing original bytes and invalid reader references."""
    from app.services.reader_extraction import ReaderConversionError, reader_representation, sha256
    rows = []
    for document in documents:
        try:
            path, reference = reader_representation(document)
            if (not Path(document.storage_path).is_file() or
                    sha256(document.storage_path) != reference['source_sha256'] or sha256(path) != reference['sha256']):
                continue
        except (ReaderConversionError, OSError):
            continue
        rows.extend(document_passages(document))
    return rows


def cached_embedding(passage, snapshot, document, model_key):
    cache = document.extracted_text[passage.page - 1].get('search', {})
    if not isinstance(cache, dict) or cache.get('revision') != snapshot.revision or cache.get('model') != model_key:
        return None
    entries = cache.get('passages', {})
    return entries.get(f'{passage.start}:{passage.end}') if isinstance(entries, dict) else None


def save_embeddings(rows, model_key):
    """Reassign JSON only after all provider output has been validated."""
    updates = {}
    for passage, snapshot, document in rows:
        if document.id not in updates:
            updates[document.id] = (document, deepcopy(document.extracted_text))
        pages = updates[document.id][1]
        page = pages[passage.page - 1]
        cache = page.get('search', {})
        if (not isinstance(cache, dict) or cache.get('revision') != snapshot.revision or
                cache.get('model') != model_key or not isinstance(cache.get('passages'), dict)):
            cache = {'revision': snapshot.revision, 'model': model_key, 'passages': {}}
            page['search'] = cache
        cache['passages'][f'{passage.start}:{passage.end}'] = passage.embedding
    for document, pages in updates.values():
        if pages != document.extracted_text:
            document.extracted_text = pages


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
    candidates = db.query(Document).filter(Document.owner_id == owner_id, Document.expires_at > now)
    if folder_id is not None:
        candidates = candidates.filter(Document.folder_id == folder_id)
    if label is not None:
        # A manual correction supersedes the predicted label. Equality avoids
        # treating wildcard characters supplied by the user as a broad match.
        effective_label = func.coalesce(func.nullif(func.trim(Document.user_label), ''), Document.ai_label)
        candidates = candidates.filter(func.lower(effective_label) == label.lower())
    if mode == 'semantic':
        # Cache writes share the source JSON column. Serialize them with extraction
        # updates so a slow embedding request cannot overwrite newer saved pages.
        candidates = candidates.with_for_update()
    terms = set(tokens(query))
    if mode == 'content':
        if not terms:
            return SearchResponse(query=query, total_hits=0)
    rows = authorized_passages(candidates.all())
    if mode == 'content':
        rows = [row for row in rows if terms.intersection(tokens(row[0].text))]
    scored = []
    if mode == 'semantic' and rows:
        for passage, snapshot, document in rows:
            passage.embedding = cached_embedding(passage, snapshot, document, embedder.model_key)
        missing = [passage for passage, _, _ in rows if passage.embedding is None]
        if missing:
            vectors = embedder.embed([passage.text for passage in missing], task='RETRIEVAL_DOCUMENT')
            if len(vectors) != len(missing):
                raise ValueError('Embedding count does not match indexed passages.')
            validated = [normalized_vector(vector) for vector in vectors]
            for passage, vector in zip(missing, validated):
                passage.embedding = vector
        vector = normalized_vector(embedder.embed([query], task='RETRIEVAL_QUERY')[0])
        for passage, snapshot, document in rows:
            stored = normalized_vector(passage.embedding)
            if len(stored) != len(vector):
                raise ValueError('Search embedding dimensions differ.')
            score = sum(left * right for left, right in zip(vector, stored))
            if score >= MIN_SEMANTIC_SCORE:
                scored.append((score, passage, snapshot, document))
        save_embeddings(rows, embedder.model_key)
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
