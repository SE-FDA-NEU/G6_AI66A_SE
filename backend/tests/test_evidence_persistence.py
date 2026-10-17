"""Tests for evidence persistence, distinct references across multiple documents,
retrievable evidence in job responses, and search hit reference equivalence.
"""
from copy import deepcopy
import pytest

from app.models import Citation, Document, Job
from app.schemas.search import (
    SearchHit,
    SourceReference,
    evidence_to_source_reference,
    search_hit_to_evidence,
)
from app.services.processing import process_job
from app.services.reader_extraction import extract_document_for_reader
from test_pdf_extraction import make_pdf


@pytest.fixture
def multi_doc_job(client, session_factory, tmp_path):
    """Fixture creating a job with two distinct documents containing facts."""
    pdf1 = make_pdf(tmp_path / 'doc1.pdf', [
        b'BT /F1 12 Tf 72 720 Td (Penalty 0.05% per day for delay.) Tj ET',
        b'BT /F1 12 Tf 72 720 Td (Total amount 1000 USD paid on 01/03/2026.) Tj ET',
    ])
    pdf2 = make_pdf(tmp_path / 'doc2.pdf', [
        b'BT /F1 12 Tf 72 720 Td (Late fee 0.05% per day applies.) Tj ET',
        b'BT /F1 12 Tf 72 720 Td (Signed and verified 01/03/2026.) Tj ET',
        b'BT /F1 12 Tf 72 720 Td (Alternative penalty 0.05% per day.) Tj ET',
    ])

    uploaded = client.post('/upload', files=[
        ('files', ('doc1.pdf', pdf1.read_bytes(), 'application/pdf')),
        ('files', ('doc2.pdf', pdf2.read_bytes(), 'application/pdf')),
    ])
    assert uploaded.status_code == 202
    job_id = int(uploaded.json()['jobId'])

    with session_factory() as db:
        job = db.get(Job, job_id)
        ids = [jf.document_id for jf in job.job_files]

    pages = {}
    for doc_id in ids:
        pages[doc_id] = extract_document_for_reader(doc_id, session_factory)['extracted_text']

    return job_id, ids, pages


def build_evidence(pages, document_id, page=1, quote=None):
    page_data = pages[document_id][page - 1]
    text = quote or page_data['text']
    start = page_data['text'].index(text)
    return {
        'document_id': document_id,
        'page': page,
        'start': start,
        'end': start + len(text),
        'quote': text,
        'reader_version': page_data['reader']['sha256'],
    }


def test_two_documents_supporting_one_bullet_claim_persist_distinct_citations(client, session_factory, multi_doc_job):
    job_id, (doc1_id, doc2_id), pages = multi_doc_job

    ev1 = build_evidence(pages, doc1_id, page=1, quote='0.05% per day')
    ev2 = build_evidence(pages, doc2_id, page=1, quote='0.05% per day')

    claim = {
        'text': 'Late fee is 0.05% per day.',
        'evidence': [ev1, ev2],
        'unverified': False,
    }

    async def analyzer(document, _):
        if document.id == doc1_id:
            return {'output': {'type': 'bullet', 'bullets': [claim], 'actions': []}}
        return {'output': {'type': 'bullet', 'bullets': [], 'actions': []}}

    process_job(job_id, session_factory, analyzer=analyzer)

    # 1. Verify API response
    response = client.get(f'/jobs/{job_id}')
    assert response.status_code == 200
    saved = response.json()
    assert saved['status'] == 'completed'
    assert len(saved['citations']) == 2

    # Verify both documents are distinct in the citations
    citations = saved['citations']
    doc_ids = {c['document_id'] for c in citations}
    doc_names = {c['doc_name'] for c in citations}
    assert doc_ids == {doc1_id, doc2_id}
    assert doc_names == {'doc1.pdf', 'doc2.pdf'}
    assert all(c['claim_text'] == 'Late fee is 0.05% per day.' for c in citations)
    assert all(not c['unverified'] for c in citations)
    assert all(c['page'] == 1 for c in citations)
    assert all(c['text_span'] == '0.05% per day' for c in citations)

    # 2. Verify direct Database persistence
    with session_factory() as db:
        db_citations = db.query(Citation).filter_by(job_id=job_id).all()
        assert len(db_citations) == 2
        assert {c.document_id for c in db_citations} == {doc1_id, doc2_id}
        assert {c.doc_name for c in db_citations} == {'doc1.pdf', 'doc2.pdf'}
        assert all(c.claim_text == 'Late fee is 0.05% per day.' for c in db_citations)

    # 3. Verify retrievable evidence in result_data
    doc1_result = saved['result_data']['documents'][str(doc1_id)]
    bullets = doc1_result['output']['bullets']
    assert len(bullets) == 1
    assert len(bullets[0]['evidence']) == 2
    assert bullets[0]['evidence'][0]['document_id'] == doc1_id
    assert bullets[0]['evidence'][1]['document_id'] == doc2_id


def test_two_documents_supporting_table_cell_persist_distinct_citations(client, session_factory, multi_doc_job):
    job_id, (doc1_id, doc2_id), pages = multi_doc_job

    with session_factory() as db:
        db.get(Job, job_id).mode = 'table'
        db.commit()

    ev1 = build_evidence(pages, doc1_id, page=1, quote='0.05% per day')
    ev2 = build_evidence(pages, doc2_id, page=3, quote='0.05% per day')

    penalty_cell = {
        'text': '0.05% per day',
        'evidence': [ev1, ev2],
        'unverified': False,
    }

    async def analyzer(document, _):
        if document.id == doc1_id:
            return {'output': {'type': 'table', 'penalty': penalty_cell}}
        return {'output': {'type': 'table'}}

    process_job(job_id, session_factory, analyzer=analyzer)

    response = client.get(f'/jobs/{job_id}')
    assert response.status_code == 200
    saved = response.json()
    assert saved['status'] == 'completed'

    citations = saved['citations']
    assert len(citations) == 2
    assert {(c['document_id'], c['page']) for c in citations} == {(doc1_id, 1), (doc2_id, 3)}
    assert {c['doc_name'] for c in citations} == {'doc1.pdf', 'doc2.pdf'}


def test_two_documents_supporting_concept_persist_distinct_citations(client, session_factory, multi_doc_job):
    job_id, (doc1_id, doc2_id), pages = multi_doc_job

    with session_factory() as db:
        db.get(Job, job_id).mode = 'concept'
        db.commit()

    ev1 = build_evidence(pages, doc1_id, page=1, quote='0.05% per day')
    ev2 = build_evidence(pages, doc2_id, page=1, quote='0.05% per day')

    concept_desc = {
        'text': '0.05% per day',
        'evidence': [ev1, ev2],
        'unverified': False,
    }

    async def analyzer(document, _):
        if document.id == doc1_id:
            return {'output': {'type': 'concept', 'concepts': [
                {'name': 'Penalty Clause', 'description': concept_desc}
            ]}}
        return {'output': {'type': 'concept', 'concepts': []}}

    process_job(job_id, session_factory, analyzer=analyzer)

    response = client.get(f'/jobs/{job_id}')
    assert response.status_code == 200
    saved = response.json()
    assert saved['status'] == 'completed'

    citations = saved['citations']
    assert len(citations) == 2
    assert {c['doc_name'] for c in citations} == {'doc1.pdf', 'doc2.pdf'}
    assert {c['document_id'] for c in citations} == {doc1_id, doc2_id}


def test_retrievable_evidence_in_job_response_enables_reader_navigation(client, session_factory, multi_doc_job):
    job_id, (doc1_id, doc2_id), pages = multi_doc_job

    ev1 = build_evidence(pages, doc1_id, page=2, quote='1000 USD')
    ev2 = build_evidence(pages, doc2_id, page=2, quote='01/03/2026')

    async def analyzer(document, _):
        if document.id == doc1_id:
            return {'output': {'type': 'bullet', 'bullets': [
                {'text': 'Amount 1000 USD on 01/03/2026', 'evidence': [ev1, ev2], 'unverified': False}
            ], 'actions': []}}
        return {'output': {'type': 'bullet', 'bullets': [], 'actions': []}}

    process_job(job_id, session_factory, analyzer=analyzer)

    saved = client.get(f'/jobs/{job_id}').json()
    claim_evidence = saved['result_data']['documents'][str(doc1_id)]['output']['bullets'][0]['evidence']

    for ev in claim_evidence:
        # Verify all retrievable fields are present
        assert ev['document_id'] in (doc1_id, doc2_id)
        assert ev['page'] == 2
        assert ev['start'] >= 0
        assert ev['end'] > ev['start']
        assert ev['end'] - ev['start'] == len(ev['quote'])
        assert len(ev['reader_version']) == 64

        # Verify reader page endpoint serves the target document and page
        page_res = client.get(f"/documents/{ev['document_id']}/pages")
        assert page_res.status_code == 200
        page_json = page_res.json()
        assert page_json['page_count'] >= ev['page']
        assert page_json['reader_version'] == ev['reader_version']

        # Verify exact quote matches reader text at offsets
        page_text = page_json['pages'][ev['page'] - 1]['text']
        assert page_text[ev['start']:ev['end']] == ev['quote']

        # Verify reader PDF endpoint returns 200 with the version
        pdf_res = client.get(f"/documents/{ev['document_id']}/reader.pdf?version={ev['reader_version']}")
        assert pdf_res.status_code == 200


def test_search_hit_source_reference_equivalence():
    """Verify SearchHit provides equivalent source reference contract to Evidence and Citation."""
    hit = SearchHit(
        document_id=42,
        doc_name="contract.pdf",
        page=3,
        start=15,
        end=28,
        snippet="0.05% per day",
        reader_version="a" * 64,
        highlight_url="/documents/42?page=3&start=15&end=28",
        score=0.95,
        ai_label="Hợp đồng",
    )

    # Convert search hit to Evidence (reusable by claim validation)
    evidence = search_hit_to_evidence(hit)
    assert evidence.document_id == 42
    assert evidence.page == 3
    assert evidence.start == 15
    assert evidence.end == 28
    assert evidence.quote == "0.05% per day"
    assert evidence.reader_version == "a" * 64

    # Convert Evidence back to universal SourceReference with doc_name
    source_ref = evidence_to_source_reference(evidence, hit.doc_name)
    assert source_ref.document_id == hit.document_id
    assert source_ref.doc_name == hit.doc_name
    assert source_ref.page == hit.page
    assert source_ref.start == hit.start
    assert source_ref.end == hit.end
    assert source_ref.snippet == hit.snippet
    assert source_ref.reader_version == hit.reader_version
    assert source_ref.highlight_url == hit.highlight_url
