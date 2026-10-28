"""Evidence contract against real PDFs, ownership, multiple sources and reload."""
from copy import deepcopy

import pytest

from app.core.security import create_access_token
from app.models import Citation, Document, Job
from app.services.evidence import literal_facts
from app.services.processing import process_job
from app.services.reader_extraction import extract_document_for_reader
from test_pdf_extraction import make_pdf


@pytest.fixture
def evidence_job(client, session_factory, tmp_path):
    source = make_pdf(tmp_path / 'facts.pdf', [
        b'BT /F1 12 Tf 72 720 Td (Value 1000 USD. Signed 01/03/2026.) Tj ET',
        b'BT /F1 12 Tf 72 720 Td (Late fee 0.05% per day. Payment within 30 days.) Tj ET',
        b'BT /F1 12 Tf 72 720 Td (Value 1000 USD. Signed 01/03/2026.) Tj ET',
        b'BT /F1 12 Tf 72 720 Td (The tenant may terminate with notice.) Tj ET',
        b'',
    ])
    uploaded = client.post('/upload', files=[
        ('files', (name, source.read_bytes(), 'application/pdf')) for name in ('first.pdf', 'second.pdf')
    ])
    assert uploaded.status_code == 202
    job_id = int(uploaded.json()['jobId'])
    with session_factory() as db:
        ids = [link.document_id for link in db.get(Job, job_id).job_files]
    pages = {}
    for document_id in ids:
        pages[document_id] = extract_document_for_reader(document_id, session_factory)['extracted_text']
    return job_id, ids, pages


def reference(pages, document_id, page=1, text=None):
    source = pages[document_id][page - 1]
    quote = text or source['text']
    start = source['text'].index(quote)
    return {'document_id': document_id, 'page': page, 'start': start, 'end': start + len(quote),
            'quote': quote, 'reader_version': source['reader']['sha256']}


def run_claim(client, session_factory, context, claim, mode='bullet'):
    job_id, ids, _ = context
    with session_factory() as db:
        db.get(Job, job_id).mode = mode
        db.commit()
    async def analyzer(document, requested):
        included = claim if document.id == ids[0] else None
        if mode == 'bullet':
            output = {'type': mode, 'bullets': [included] if included else []}
        elif mode == 'concept':
            output = {'type': mode, 'concepts': [{'name': 'Contract fact', 'description': included}] if included else []}
        else:
            output = {'type': mode, **({'penalty': included} if included else {})}
        return {'output': output}
    process_job(job_id, session_factory, analyzer=analyzer)
    response = client.get(f'/jobs/{job_id}')
    assert response.status_code == 200
    saved = response.json()
    assert saved['status'] == 'completed' and saved['completed_count'] == 2
    output = saved['result_data']['documents'][str(ids[0])]['output']
    actual = output['bullets'][0] if mode == 'bullet' else output['penalty'] if mode == 'table' else output['concepts'][0]['description']
    assert client.get(f'/jobs/{job_id}').json() == saved
    return actual, saved


@pytest.mark.parametrize('mode', ['bullet', 'table', 'concept'])
@pytest.mark.parametrize('state', [
    pytest.param('valid', id='TC-US08-01-correct-document-page'),
    pytest.param('missing', id='TC-US08-02-missing-evidence-unverified'),
    pytest.param('invalid', id='TC-US08-03-invalid-page-rejected'),
])
def test_shared_contract_marks_missing_invalid_sources_unverified_in_every_mode(client, session_factory, evidence_job, mode, state):
    job_id, ids, pages = evidence_job
    evidence = reference(pages, ids[0], 2, '0.05% per day')
    if state == 'invalid':
        evidence['page'] = 5  # real textless page cannot support a factual amount
    claim = {'text': '0.05% per day', 'evidence': [] if state == 'missing' else [evidence], 'unverified': False}
    actual, saved = run_claim(client, session_factory, evidence_job, claim, mode)
    assert actual['text'] == claim['text'] == '0.05% per day'
    assert actual['kind'] == ('percentage' if state == 'valid' else 'general')
    assert actual['unverified'] == (state != 'valid')
    if state == 'valid':
        assert actual['evidence'] == [evidence] and actual['verification_issues'] == []
    else:
        assert actual['evidence'] == []
        assert ('missing_evidence' if state == 'missing' else 'invalid_evidence') in actual['verification_issues']
        assert 'unverified_claims' in saved['result_data']['documents'][str(ids[0])]['warnings']
        assert all(citation['unverified'] and citation['page'] is None for citation in saved['citations'])
    assert len(saved['citations']) == 1
    citation = saved['citations'][0]
    assert citation['document_id'] == ids[0]
    assert citation['doc_name'] == 'first.pdf'
    assert citation['claim_text'] == claim['text']
    assert citation['unverified'] == (state != 'valid')
    assert citation['page'] == (2 if state == 'valid' else None)
    assert citation['text_span'] == (evidence['quote'] if state == 'valid' else None)
    if state == 'valid':
        page_response = client.get(f'/documents/{ids[0]}/pages/2/text')
        assert page_response.status_code == 200
        source = page_response.json()
        assert source['document_id'] == evidence['document_id']
        assert source['page'] == evidence['page']
        assert source['text'][evidence['start']:evidence['end']] == evidence['quote']
    with session_factory() as db:
        persisted = db.query(Citation).filter_by(job_id=job_id).one()
        assert persisted.document_id == citation['document_id']
        assert persisted.page == citation['page']
        assert persisted.text_span == citation['text_span']
        assert persisted.claim_text == claim['text']
        assert persisted.unverified == actual['unverified']


@pytest.mark.parametrize('kind,text,page', [
    ('amount', '1000 USD', 1), ('date', '01/03/2026', 1), ('percentage', '0.05% per day', 2),
    ('clause', 'The tenant may terminate with notice.', 4),
])
def test_amount_date_percentage_and_contract_clause_contract(client, session_factory, evidence_job, kind, text, page):
    _, ids, pages = evidence_job
    claim = {'kind': kind, 'text': text, 'unverified': False, 'evidence': [reference(pages, ids[0], page)]}
    actual, _ = run_claim(client, session_factory, evidence_job, claim)
    assert actual['kind'] == kind and actual['unverified'] is False
    assert actual['evidence'][0]['page'] == page


@pytest.mark.parametrize('text,page', [
    ('5% per day', 2), ('0.05% per month', 2), ('Payment within 30 months', 2),
    ('1000 VND', 1), ('10000 USD', 1), ('Signed 01/04/2026', 1),
])
def test_valid_passage_does_not_verify_changed_factual_values(client, session_factory, evidence_job, text, page):
    _, ids, pages = evidence_job
    claim = {'text': text, 'unverified': False, 'evidence': [reference(pages, ids[0], page)]}
    actual, saved = run_claim(client, session_factory, evidence_job, claim)
    assert actual['unverified'] and 'unsupported_fact' in actual['verification_issues']
    assert actual['evidence']  # genuine passage remains available for human review
    assert saved['citations'][0]['unverified']


@pytest.mark.parametrize('bad', ['negative_span', 'beyond_page', 'empty_quote', 'wrong_quote', 'missing_span',
                               'missing_page', 'missing_document', 'bool_page', 'numeric_string', 'wrong_version'])
def test_invalid_reference_fields_are_discarded_without_echoing_fake_citations(client, session_factory, evidence_job, bad):
    _, ids, pages = evidence_job
    evidence = reference(pages, ids[0])
    if bad == 'negative_span':
        evidence['start'] = -1
    elif bad == 'beyond_page':
        evidence['start'], evidence['end'] = 500, 500 + len(evidence['quote'])
    elif bad == 'empty_quote':
        evidence['quote'] = ''
    elif bad == 'wrong_quote':
        evidence['quote'] = 'X' * len(evidence['quote'])
    elif bad.startswith('missing_'):
        evidence.pop({'missing_span': 'start', 'missing_page': 'page', 'missing_document': 'document_id'}[bad])
    elif bad == 'bool_page':
        evidence['page'] = True
    elif bad == 'numeric_string':
        evidence['document_id'] = str(ids[0])
    else:
        evidence['reader_version'] = '0' * 64
    actual, saved = run_claim(client, session_factory, evidence_job,
                              {'text': '1000 USD', 'evidence': [evidence], 'unverified': False})
    assert actual['unverified'] and actual['evidence'] == []
    assert 'invalid_evidence' in actual['verification_issues']
    assert all(citation['page'] is None and citation['text_span'] is None for citation in saved['citations'])


def test_same_claim_keeps_separate_documents_pages_and_repeated_source_text(client, session_factory, evidence_job):
    _, ids, pages = evidence_job
    first = reference(pages, ids[0], 1)
    references = [first, reference(pages, ids[0], 3), reference(pages, ids[1], 1), deepcopy(first)]
    actual, saved = run_claim(client, session_factory, evidence_job,
                              {'text': '1000 USD', 'evidence': references, 'unverified': False})
    assert not actual['unverified'] and actual['evidence'] == references[:3]
    assert len(saved['citations']) == 3
    assert {(item['document_id'], item['page']) for item in saved['citations']} == {(ids[0], 1), (ids[0], 3), (ids[1], 1)}
    assert {item['doc_name'] for item in saved['citations']} == {'first.pdf', 'second.pdf'}
    assert len({item['text_span'] for item in saved['citations']}) == 1
    # Completing the second file must not delete the first claim's source there.
    assert saved['job_files'][1]['status'] == 'completed'


def test_valid_and_invalid_sources_preserve_only_real_passages_for_review(client, session_factory, evidence_job):
    _, ids, pages = evidence_job
    valid = reference(pages, ids[0])
    invalid = {**valid, 'document_id': 99999, 'quote': 'private invented quote'}
    actual, _ = run_claim(client, session_factory, evidence_job,
                          {'text': '1000 USD', 'evidence': [invalid, valid], 'unverified': False})
    assert actual['unverified'] and actual['evidence'] == [valid]
    assert actual['verification_issues'] == ['invalid_evidence']


def test_another_users_document_is_not_a_valid_source_even_with_matching_text(client, session_factory, evidence_job):
    _, ids, pages = evidence_job
    with session_factory() as db:
        db.get(Document, ids[1]).owner_id = 124
        db.commit()
    # Invoke the shared validator directly: the job runner also refuses to
    # process a tampered JobFile pointing at a different user's document.
    from app.services.evidence import EvidenceValidator
    from app.services.job_extraction import PreparedExtraction
    from app.schemas.result import Claim
    from app.services.reader_extraction import reader_representation
    with session_factory() as db:
        job = db.get(Job, evidence_job[0])
        current = db.get(Document, ids[0])
        path, _ = reader_representation(current)
        prepared = PreparedExtraction({'page_count': current.page_count, 'extracted_text': current.extracted_text}, path)
        claim = Claim(text='1000 USD', evidence=[reference(pages, ids[1])], unverified=False)
        validated = EvidenceValidator(db, job, current, prepared).validate(claim)
        assert validated.unverified and validated.evidence == []
    async def analyzer(document, _):
        assert document.id != ids[1], 'Foreign document must not reach the analyzer'
        return {'output': {'type': 'bullet'}}
    process_job(evidence_job[0], session_factory, analyzer=analyzer)
    saved = client.get(f'/jobs/{evidence_job[0]}').json()
    assert saved['status'] == 'failed' and saved['completed_count'] == 1
    assert saved['job_files'][1]['status'] == 'failed'
    foreign = client.get(f'/jobs/{evidence_job[0]}', headers={'Authorization': f"Bearer {create_access_token({'sub': '124'})}"})
    assert foreign.status_code == 404


def test_model_uncertainty_is_never_promoted_to_verified(client, session_factory, evidence_job):
    _, ids, pages = evidence_job
    actual, _ = run_claim(client, session_factory, evidence_job,
                          {'text': '1000 USD', 'evidence': [reference(pages, ids[0])], 'unverified': True})
    assert actual['unverified'] and actual['verification_issues'] == ['model_uncertain']


def test_concept_heading_cannot_hide_an_unsupported_percentage(client, session_factory, evidence_job):
    _, ids, pages = evidence_job
    async def analyzer(document, _):
        return {'output': {'type': 'concept', 'concepts': [{
            'name': 'Penalty 5% per day',
            'description': {'text': '0.05% per day', 'unverified': False,
                            'evidence': [reference(pages, document.id, 2)]},
        }]}}
    with session_factory() as db:
        db.get(Job, evidence_job[0]).mode = 'concept'
        db.commit()
    process_job(evidence_job[0], session_factory, analyzer=analyzer)
    saved = client.get(f'/jobs/{evidence_job[0]}').json()
    claim = saved['result_data']['documents'][str(ids[0])]['output']['concepts'][0]['description']
    assert claim['unverified'] and 'unsupported_fact' in claim['verification_issues']


def test_numeric_comparisons_are_conservative_about_decimal_and_date_reformats():
    assert ('percentage', '0.05%') in literal_facts('0.05 percent per day')
    assert ('rate_period', '0.05%/day') in literal_facts('0.05% mỗi ngày')
    assert ('duration', '30/day') in literal_facts('trong 30 ngày')
    assert literal_facts('100.') == {('number', '100')}
    assert literal_facts('01/03/2026') != literal_facts('03/01/2026')
    assert literal_facts('0.05%') != literal_facts('5%')
