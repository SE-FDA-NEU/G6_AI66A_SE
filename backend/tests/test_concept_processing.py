"""Tests for concept processing (BR04, BR05).

- Three to five core concepts grounded in the source.
- Persist structured concepts and evidence using the shared result contract.
- If the source cannot support the requested overview, return a clear limitation
  instead of inventing concepts.
- Test concept counts and evidence validity.
"""
import asyncio
from dataclasses import replace
import json
import pytest

from app.core.config import settings
from app.models import Citation, Document, FileFormat, Job, JobMode
from app.schemas.result import (
    AnalysisResult,
    Claim,
    Concept,
    ConceptOutput,
    Evidence,
    LabelSuggestion,
)
from app.services import gemini_analysis as gemini, processing
from app.services.evidence import parse_analysis
from app.services.processing import DocumentInput, process_job
from app.services.reader_extraction import extract_document_for_reader
from app.services.result_persistence import InvalidAnalysisResult, save_analysis
from test_pdf_extraction import make_pdf


@pytest.fixture
def concept_job(client, session_factory, tmp_path):
    """Fixture creating a job with an uploaded paper for concept extraction."""
    pdf = make_pdf(tmp_path / 'macro_paper.pdf', [
        b'BT /F1 12 Tf 72 720 Td (Demand-pull inflation occurs when aggregate demand outpaces supply.) Tj ET',
        b'BT /F1 12 Tf 72 720 Td (Cost-push inflation is driven by aggregate supply decreases.) Tj ET',
        b'BT /F1 12 Tf 72 720 Td (Monetary policy adjusts interest rates to stabilize price levels.) Tj ET',
        b'BT /F1 12 Tf 72 720 Td (Fiscal policy uses government spending and taxation to influence demand.) Tj ET',
        b'BT /F1 12 Tf 72 720 Td (Exchange rate pass-through affects domestic consumer price index by 15%.) Tj ET',
    ])

    uploaded = client.post('/upload', data={'mode': 'concept'}, files=[
        ('files', ('macro_paper.pdf', pdf.read_bytes(), 'application/pdf')),
    ])
    assert uploaded.status_code == 202
    job_id = int(uploaded.json()['jobId'])

    with session_factory() as db:
        job = db.get(Job, job_id)
        doc_id = job.job_files[0].document_id

    pages = extract_document_for_reader(doc_id, session_factory)['extracted_text']
    return job_id, doc_id, pages


def build_evidence(pages, doc_id, page_num, quote):
    page_data = pages[page_num - 1]
    start = page_data['text'].index(quote)
    return {
        'document_id': doc_id,
        'page': page_num,
        'start': start,
        'end': start + len(quote),
        'quote': quote,
        'reader_version': page_data['reader']['sha256'],
    }


@pytest.mark.parametrize('concept_count', [3, 4, 5])
def test_three_to_five_concepts_persisted_with_grounded_evidence(client, session_factory, concept_job, concept_count):
    job_id, doc_id, pages = concept_job

    concept_definitions = [
        ('Demand-pull Inflation', 'Demand-pull inflation occurs when aggregate demand outpaces supply.', 1),
        ('Cost-push Inflation', 'Cost-push inflation is driven by aggregate supply decreases.', 2),
        ('Monetary Policy', 'Monetary policy adjusts interest rates to stabilize price levels.', 3),
        ('Fiscal Policy', 'Fiscal policy uses government spending and taxation to influence demand.', 4),
        ('Exchange Rate Pass-through', 'Exchange rate pass-through affects domestic consumer price index by 15%.', 5),
    ]

    selected_concepts = concept_definitions[:concept_count]
    concepts = []
    for name, quote, page_num in selected_concepts:
        ev = build_evidence(pages, doc_id, page_num, quote)
        concepts.append({
            'name': name,
            'description': {
                'text': quote,
                'evidence': [ev],
                'unverified': False,
            },
        })

    async def analyzer(document, _):
        return {
            'output': {
                'type': 'concept',
                'concepts': concepts,
            },
            'label': {'ai_label': 'Macroeconomics', 'ai_confidence': 0.88},
        }

    process_job(job_id, session_factory, analyzer=analyzer)

    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'completed'
    doc_result = saved['result_data']['documents'][str(doc_id)]
    assert doc_result['output']['type'] == 'concept'
    persisted_concepts = doc_result['output']['concepts']
    assert len(persisted_concepts) == concept_count

    # Verify each concept is grounded and verified
    for idx, c in enumerate(persisted_concepts):
        assert c['name'] == selected_concepts[idx][0]
        assert c['description']['text'] == selected_concepts[idx][1]
        assert c['description']['unverified'] is False
        assert len(c['description']['evidence']) == 1
        assert c['description']['evidence'][0]['quote'] == selected_concepts[idx][1]

    # Verify citations in DB
    citations = saved['citations']
    assert len(citations) == concept_count
    for cit in citations:
        assert cit['unverified'] is False
        assert cit['document_id'] == doc_id
        assert cit['doc_name'] == 'macro_paper.pdf'


def test_more_than_five_concepts_rejected_by_shared_contract(client, session_factory, concept_job):
    job_id, doc_id, pages = concept_job

    # Attempt to submit 6 concepts (exceeding BR04 3-5 limit)
    six_concepts = []
    for i in range(1, 7):
        ev = build_evidence(pages, doc_id, 1, 'Demand-pull inflation')
        six_concepts.append({
            'name': f'Concept {i}',
            'description': {
                'text': 'Demand-pull inflation',
                'evidence': [ev],
                'unverified': False,
            },
        })

    async def analyzer(document, _):
        return {
            'output': {
                'type': 'concept',
                'concepts': six_concepts,
            },
        }

    process_job(job_id, session_factory, analyzer=analyzer)

    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'failed'
    assert saved['job_files'][0]['status'] == 'failed'
    assert 'invalid_result' in saved['job_files'][0]['error_message']

    # Also directly verify schema rejects 6 concepts
    with pytest.raises(Exception):
        parse_analysis({
            'output': {
                'type': 'concept',
                'concepts': six_concepts,
            },
        })


def test_short_source_returns_clear_limitation_without_inventing_concepts(client, session_factory, concept_job):
    job_id, doc_id, pages = concept_job

    # The paper is very short or can only substantiate 1 core concept
    single_quote = 'Demand-pull inflation occurs when aggregate demand outpaces supply.'
    ev = build_evidence(pages, doc_id, 1, single_quote)
    single_concept = [{
        'name': 'Demand-pull Inflation',
        'description': {
            'text': single_quote,
            'evidence': [ev],
            'unverified': False,
        },
    }]

    async def analyzer(document, _):
        # Returns 1 concept with an explicit limitation explaining why 3-5 could not be formed
        return {
            'output': {
                'type': 'concept',
                'concepts': single_concept,
                'limitation': 'Tài liệu nguồn quá ngắn, chỉ hỗ trợ xác thực 1 khái niệm chính duy nhất.',
            },
        }

    process_job(job_id, session_factory, analyzer=analyzer)

    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'completed'
    doc_result = saved['result_data']['documents'][str(doc_id)]

    # Concepts were NOT padded or invented to reach 3
    assert len(doc_result['output']['concepts']) == 1
    assert doc_result['output']['concepts'][0]['name'] == 'Demand-pull Inflation'
    assert doc_result['output']['concepts'][0]['description']['unverified'] is False

    # Clear limitation is present
    assert doc_result['output']['limitation'] == 'Tài liệu nguồn quá ngắn, chỉ hỗ trợ xác thực 1 khái niệm chính duy nhất.'
    assert 'insufficient_concepts' in doc_result['warnings']


def test_source_with_zero_concepts_returns_limitation_and_warning(client, session_factory, concept_job):
    job_id, doc_id, pages = concept_job

    async def analyzer(document, _):
        return {
            'output': {
                'type': 'concept',
                'concepts': [],
                'limitation': 'Không có đủ thông tin nền tảng để tạo lập các khái niệm cốt lõi.',
            },
        }

    process_job(job_id, session_factory, analyzer=analyzer)

    saved = client.get(f'/jobs/{job_id}').json()
    assert saved['status'] == 'completed'
    doc_result = saved['result_data']['documents'][str(doc_id)]
    assert doc_result['output']['concepts'] == []
    assert doc_result['output']['limitation'] == 'Không có đủ thông tin nền tảng để tạo lập các khái niệm cốt lõi.'
    assert 'insufficient_concepts' in doc_result['warnings']


def test_concept_evidence_validity_and_unsupported_heading_facts(client, session_factory, concept_job):
    job_id, doc_id, pages = concept_job

    # 1. Concept with heading asserting 25% while source quote only says 15%
    ev1 = build_evidence(pages, doc_id, 5, 'Exchange rate pass-through affects domestic consumer price index by 15%.')
    bad_heading_concept = {
        'name': 'Exchange Rate Pass-through of 25%',
        'description': {
            'text': 'Exchange rate pass-through affects domestic consumer price index by 15%.',
            'evidence': [ev1],
            'unverified': False,
        },
    }

    # 2. Concept with invalid offsets (quote does not match slice)
    bad_offset_concept = {
        'name': 'Monetary Policy',
        'description': {
            'text': 'Monetary policy adjusts interest rates.',
            'evidence': [{
                'document_id': doc_id,
                'page': 3,
                'start': 0,
                'end': 50,
                'quote': 'Wrong quote not matching page text at all',
                'reader_version': pages[2]['reader']['sha256'],
            }],
            'unverified': False,
        },
    }

    # 3. Grounded valid concept
    ev3 = build_evidence(pages, doc_id, 1, 'Demand-pull inflation occurs when aggregate demand outpaces supply.')
    valid_concept = {
        'name': 'Demand-pull Inflation',
        'description': {
            'text': 'Demand-pull inflation occurs when aggregate demand outpaces supply.',
            'evidence': [ev3],
            'unverified': False,
        },
    }

    async def analyzer(document, _):
        return {
            'output': {
                'type': 'concept',
                'concepts': [bad_heading_concept, bad_offset_concept, valid_concept],
            },
        }

    process_job(job_id, session_factory, analyzer=analyzer)

    saved = client.get(f'/jobs/{job_id}').json()
    doc_result = saved['result_data']['documents'][str(doc_id)]
    concepts = doc_result['output']['concepts']

    # Concept 1: bad heading has unsupported_fact
    assert concepts[0]['description']['unverified'] is True
    assert 'unsupported_fact' in concepts[0]['description']['verification_issues']

    # Concept 2: invalid offset has invalid_evidence / missing_evidence
    assert concepts[1]['description']['unverified'] is True
    assert any(issue in ('invalid_evidence', 'missing_evidence') for issue in concepts[1]['description']['verification_issues'])

    # Concept 3: fully verified
    assert concepts[2]['description']['unverified'] is False
    assert concepts[2]['description']['verification_issues'] == []

    # Warning for unverified claims is raised
    assert 'unverified_claims' in doc_result['warnings']


def test_gemini_concept_analysis_short_text_and_no_text_layer(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', 'secret')
    monkeypatch.setattr(settings, 'STORAGE_DIR', tmp_path / 'storage')

    # 1. Test empty/no text document
    empty_doc = DocumentInput(
        id=1,
        storage_path=str(tmp_path / 'empty.pdf'),
        page_count=1,
        file_format=FileFormat.PDF,
        extracted_text=[{'page': 1, 'text': '', 'positions': [], 'reader': {'sha256': 'a' * 64, 'page_kind': 'page'}}],
        owner_id=10,
    )
    result = asyncio.run(gemini.analyze_document(empty_doc, JobMode.CONCEPT))
    assert result.output.concepts == []
    assert result.output.limitation is not None
    assert 'no_text_layer' in result.warnings
