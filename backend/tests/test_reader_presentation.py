"""Saved summaries and highlights on the actual PDF, without modifying source bytes."""
from datetime import datetime, timedelta
from io import BytesIO
import hashlib

import pypdfium2
import pytest
from pypdf import PdfReader

from app.core.security import create_access_token
from app.models import Document, FileFormat, Job, JobFile
from app.services.pdf_extraction import extract_pdf
from app.services.pdf_highlights import highlighted_pdf
from app.services.reader_extraction import extract_document_for_reader
from test_pdf_extraction import make_pdf
from test_reader_extraction import keyword_reader
from test_evidence import evidence_job, reference, run_claim


@pytest.mark.parametrize('source_page', [pytest.param(2, id='TC-US09-01-citation-opens-exact-source')])
def test_saved_citation_opens_matching_document_page_and_visible_highlight(
        client, session_factory, evidence_job, source_page):
    job_id, ids, pages = evidence_job
    evidence = reference(pages, ids[0], source_page, '0.05% per day')
    claim, saved = run_claim(client, session_factory, evidence_job,
                             {'text': '0.05% per day', 'evidence': [evidence], 'unverified': False})
    assert claim['text'] == evidence['quote']
    assert claim['evidence'] == [evidence]
    summary = client.get(f'/documents/{ids[0]}/summary', params={'job_id': job_id})
    assert summary.status_code == 200
    assert summary.json()['job_id'] == job_id
    assert summary.json()['document'] == saved['result_data']['documents'][str(ids[0])]
    response = client.get(f'/documents/{evidence["document_id"]}/reader.pdf', params={
        'version': evidence['reader_version'], 'highlight_page': evidence['page'],
        'start': evidence['start'], 'end': evidence['end'],
    })
    assert response.status_code == 200
    pdf = PdfReader(BytesIO(response.content))
    assert len(pdf.pages) == 5
    assert evidence['quote'] in pdf.pages[source_page - 1].extract_text()
    assert highlight_rectangles(pdf.pages[source_page - 1])
    assert all(not highlight_rectangles(page) for index, page in enumerate(pdf.pages)
               if index != source_page - 1)
    with pypdfium2.PdfDocument(response.content) as rendered:
        image = rendered[source_page - 1].render(scale=1).to_pil().convert('RGB')
        boxes = [position['bbox'] for position in pages[ids[0]][source_page - 1]['positions']
                 if position['start'] < evidence['end'] and position['end'] > evidence['start']]
        crop = image.crop((int(min(box[0] for box in boxes)), int(min(box[1] for box in boxes)),
                           int(max(box[2] for box in boxes)) + 1, int(max(box[3] for box in boxes)) + 1))
        assert any(red > 220 and 130 < green < 245 and blue < 210
                   for red, green, blue in (crop.getpixel((x, y))
                                           for y in range(crop.height) for x in range(crop.width)))


@pytest.mark.parametrize('invalid_source', [
    pytest.param('page', id='TC-US09-02-reject-invalid-citation-page'),
    pytest.param('document', id='TC-US09-03-reject-invalid-citation-document'),
    pytest.param('version', id='TC-US09-04-reject-stale-citation'),
])
def test_invalid_citation_is_removed_from_saved_reader_summary(
        client, session_factory, evidence_job, invalid_source):
    job_id, ids, pages = evidence_job
    evidence = reference(pages, ids[0], 2, '0.05% per day')
    evidence[{'page': 'page', 'document': 'document_id', 'version': 'reader_version'}[invalid_source]] = (
        '0' * 64 if invalid_source == 'version' else 999999)
    actual, _ = run_claim(client, session_factory, evidence_job,
                          {'text': '0.05% per day', 'evidence': [evidence], 'unverified': False})
    assert actual['text'] == '0.05% per day'
    assert actual['unverified'] is True
    assert actual['evidence'] == []
    assert 'invalid_evidence' in actual['verification_issues']
    response = client.get(f'/documents/{ids[0]}/summary', params={'job_id': job_id})
    assert response.status_code == 200
    assert response.json()['document']['output']['bullets'][0] == actual


def highlight_rectangles(page):
    """Read actual overlay rectangles from the returned PDF content stream."""
    rectangles, pending = [], []
    for operands, operator in page.get_contents().operations:
        if operator == b're':
            pending.append(tuple(float(value) for value in operands))
        elif operator in (b'f', b'f*', b'B', b'B*', b'b', b'b*'):
            rectangles.extend(pending)
            pending = []
        elif operator in (b'n', b'S', b's'):
            # PDF merging adds a page-size clipping rectangle (re W n).
            # It is not a painted search highlight.
            pending = []
    return rectangles


@pytest.mark.parametrize('page_number,query,spans', [
    pytest.param(2, 'KEYWORD', [(7, 14), (15, 22)], id='TC-US04-36-known-page-repeated-highlight'),
    pytest.param(1, 'Alpha', [(0, 5)], id='TC-US04-37-first-page-highlight'),
    pytest.param(3, 'Omega', [(10, 15)], id='TC-US04-38-last-page-highlight'),
])
def test_keyword_highlight_draws_only_at_known_match_positions(
        client, keyword_reader, page_number, query, spans):
    document_id, source, pages = keyword_reader
    original = source.read_bytes()
    version = pages[0]['reader']['sha256']
    response = client.get(f'/documents/{document_id}/reader.pdf', params={
        'version': version, 'highlight_page': page_number, 'q': query,
    })
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/pdf'
    assert response.headers['x-reader-version'] == version
    rendered = PdfReader(BytesIO(response.content))
    assert len(rendered.pages) == 3
    page = pages[page_number - 1]
    for start, end in spans:
        assert page['text'][start:end].casefold() == query.casefold()
    selected = [position for position in page['positions']
                if any(position['start'] < end and position['end'] > start for start, end in spans)]
    assert selected
    rectangles = highlight_rectangles(rendered.pages[page_number - 1])
    assert len(rectangles) == len(selected)
    height = float(rendered.pages[page_number - 1].mediabox.height)
    for rectangle, position in zip(rectangles, selected):
        x0, top, x1, bottom = position['bbox']
        assert rectangle == pytest.approx((x0, height - bottom, x1 - x0, bottom - top), abs=0.001)
    for index, rendered_page in enumerate(rendered.pages):
        assert rendered_page.extract_text().strip() == pages[index]['text']
        if index != page_number - 1:
            assert highlight_rectangles(rendered_page) == []
    assert source.read_bytes() == original


@pytest.mark.parametrize('query', [
    pytest.param('absentword', id='TC-US04-39-highlight-no-match'),
    pytest.param('', id='TC-US04-40-empty-highlight-query-clears-marks'),
])
def test_valid_query_without_highlights_returns_readable_pdf(client, keyword_reader, query):
    document_id, source, pages = keyword_reader
    original = source.read_bytes()
    version = pages[0]['reader']['sha256']
    response = client.get(f'/documents/{document_id}/reader.pdf', params={
        'version': version, 'highlight_page': 2, 'q': query,
    })
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/pdf'
    assert response.headers['x-reader-version'] == version
    pdf = PdfReader(BytesIO(response.content))
    assert len(pdf.pages) == 3
    assert [page.extract_text().strip() for page in pdf.pages] == [page['text'] for page in pages]
    assert all(highlight_rectangles(page) == [] for page in pdf.pages)
    assert source.read_bytes() == original


@pytest.mark.parametrize('page_number,start,end,query', [
    pytest.param(1, 0, 5, 'Alpha', id='TC-US04-55-valid-span-starts-at-zero'),
    pytest.param(3, 10, 15, 'Omega', id='TC-US04-56-valid-span-ends-at-text-length'),
])
def test_exact_match_span_accepts_first_and_last_character_boundaries(
        client, keyword_reader, page_number, start, end, query):
    document_id, source, pages = keyword_reader
    original = source.read_bytes()
    assert pages[page_number - 1]['text'][start:end] == query
    params = {'version': pages[0]['reader']['sha256'], 'highlight_page': page_number}
    url = f'/documents/{document_id}/reader.pdf'
    span_response = client.get(url, params={**params, 'start': start, 'end': end})
    query_response = client.get(url, params={**params, 'q': query})
    assert span_response.status_code == query_response.status_code == 200
    span_pdf = PdfReader(BytesIO(span_response.content))
    query_pdf = PdfReader(BytesIO(query_response.content))
    assert len(span_pdf.pages) == len(query_pdf.pages) == 3
    rectangles = highlight_rectangles(span_pdf.pages[page_number - 1])
    assert len(rectangles) == end - start
    assert rectangles == highlight_rectangles(query_pdf.pages[page_number - 1])
    assert all(highlight_rectangles(page) == [] for index, page in enumerate(span_pdf.pages)
               if index != page_number - 1)
    assert source.read_bytes() == original


@pytest.mark.parametrize('params,error_field,detail', [
    pytest.param({'highlight_page': 2, 'q': 'x' * 501}, 'q', None,
                 id='TC-US04-41-overlong-highlight-query'),
    pytest.param({'highlight_page': 0, 'q': 'keyword'}, 'highlight_page', None,
                 id='TC-US04-42-highlight-page-zero'),
    pytest.param({'highlight_page': -1, 'q': 'keyword'}, 'highlight_page', None,
                 id='TC-US04-43-highlight-negative-page'),
    pytest.param({'highlight_page': 4, 'q': 'keyword'}, None, 'Highlight page is outside the document.',
                 id='TC-US04-44-highlight-one-past-last-page'),
    pytest.param({'highlight_page': 'invalid', 'q': 'keyword'}, 'highlight_page', None,
                 id='TC-US04-45-highlight-nonnumeric-page'),
    pytest.param({'highlight_page': '1.5', 'q': 'keyword'}, 'highlight_page', None,
                 id='TC-US04-46-highlight-fractional-page'),
    pytest.param({'q': 'keyword'}, None, 'A highlight page is required.',
                 id='TC-US04-47-highlight-missing-page'),
    pytest.param({'highlight_page': 1, 'start': -1, 'end': 5}, 'start', None,
                 id='TC-US04-48-negative-match-start'),
    pytest.param({'highlight_page': 3, 'start': 10, 'end': 16}, None,
                 'Highlight span is outside the page text.', id='TC-US04-49-match-end-past-text'),
    pytest.param({'highlight_page': 3, 'start': 15, 'end': 16}, None,
                 'Highlight span is outside the page text.', id='TC-US04-50-match-start-at-text-end'),
    pytest.param({'highlight_page': 2, 'start': 7, 'end': 7}, None,
                 'Highlight span is outside the page text.', id='TC-US04-51-empty-match-span'),
    pytest.param({'highlight_page': 2, 'start': 14, 'end': 7}, None,
                 'Highlight span is outside the page text.', id='TC-US04-52-reversed-match-span'),
    pytest.param({'highlight_page': 2, 'start': 7}, None,
                 'Highlight span is outside the page text.', id='TC-US04-53-missing-match-end'),
    pytest.param({'highlight_page': 2, 'end': 14}, None,
                 'Highlight requires both start and end.', id='TC-US04-54-missing-match-start'),
])
def test_invalid_highlight_input_returns_validation_error_instead_of_no_match_pdf(
        client, keyword_reader, params, error_field, detail):
    document_id, source, pages = keyword_reader
    original = source.read_bytes()
    response = client.get(f'/documents/{document_id}/reader.pdf', params={
        'version': pages[0]['reader']['sha256'], **params,
    })
    assert response.status_code == 422
    assert response.headers['content-type'] == 'application/json'
    payload = response.json()
    if error_field:
        assert any(error['loc'] == ['query', error_field] for error in payload['detail'])
    else:
        assert payload['detail'] == detail
    assert source.read_bytes() == original


@pytest.mark.parametrize('rotation', [0, 90, 180, 270])
@pytest.mark.parametrize('cropbox', [None, (36, 36, 576, 756)])
def test_pdf_highlight_overlays_the_stored_glyph_coordinates(tmp_path, rotation, cropbox):
    source = make_pdf(tmp_path / 'source.pdf', [b'BT /F1 16 Tf 72 680 Td (Alpha Alpha) Tj ET'], rotation=rotation, cropbox=cropbox)
    original = source.read_bytes()
    page = extract_pdf(source)['extracted_text'][0]
    start = len(page['text']) - 5
    result = highlighted_pdf(source, page, start=start, end=start + 5)
    assert source.read_bytes() == original
    assert len(PdfReader(BytesIO(result)).pages) == 1
    # Rendering verifies visible marks on the PDF itself, including rotated/cropped pages.
    with pypdfium2.PdfDocument(result) as pdf:
        image = pdf[0].render(scale=1).to_pil().convert('RGB')
        pixels = [(x, y) for y in range(image.height) for x in range(image.width)
                  if (lambda rgb: rgb[0] > 220 and 130 < rgb[1] < 245 and rgb[2] < 210)(image.getpixel((x, y)))]
    assert pixels
    selected = [p['bbox'] for p in page['positions'] if p['start'] < start + 5 and p['end'] > start]
    origin = page['cropbox'] or page['page_bbox']
    bounds = (min(x for x, _ in pixels), min(y for _, y in pixels), max(x for x, _ in pixels), max(y for _, y in pixels))
    expected = (min(b[0] for b in selected) - origin[0], min(b[1] for b in selected) - origin[1],
                max(b[2] for b in selected) - origin[0], max(b[3] for b in selected) - origin[1])
    assert all(abs(actual - wanted) < 3 for actual, wanted in zip(bounds, expected))


@pytest.fixture
def saved_source(session_factory, tmp_path):
    source = make_pdf(tmp_path / 'source.pdf', [b'BT /F1 12 Tf 72 720 Td (Saved summary source.) Tj ET'])
    with session_factory() as db:
        doc = Document(owner_id=123, original_filename='source.pdf', storage_path=str(source), file_format=FileFormat.PDF,
                       file_size_bytes=source.stat().st_size, expires_at=datetime.now() + timedelta(days=30))
        db.add(doc); db.commit(); document_id = doc.id
    extract_document_for_reader(document_id, session_factory)
    with session_factory() as db:
        doc = db.get(Document, document_id)
        version = doc.extracted_text[0]['reader']['sha256']
        result = {'schema_version': 1, 'document_id': document_id, 'analysis_status': 'completed',
                  'original_filename': 'source.pdf', 'reader': {'version': version},
                  'output': {'type': 'bullet', 'bullets': [{'text': 'Previously saved summary.', 'unverified': True, 'evidence': []}]}}
        job = Job(owner_id=123, mode='bullet', status='completed', file_count=1, completed_count=1,
                  result_data={'documents': {str(document_id): result}})
        db.add(job); db.flush(); db.add(JobFile(job_id=job.id, document_id=document_id, status='completed'))
        db.commit()
        return document_id, job.id, version, source


def test_summary_returns_only_saved_document_result_and_enforces_ownership(client, saved_source):
    doc_id, job_id, _, _ = saved_source
    result = client.get(f'/documents/{doc_id}/summary').json()
    assert result['job_id'] == job_id
    assert result['document']['output']['bullets'][0]['text'] == 'Previously saved summary.'
    assert client.get(f'/documents/{doc_id}/summary?job_id={job_id}').json() == result
    assert client.get(f'/documents/{doc_id}/summary?job_id=999999').json()['document'] is None
    peer = {'Authorization': f"Bearer {create_access_token({'sub': '124'})}"}
    assert client.get(f'/documents/{doc_id}/summary', headers=peer).status_code == 403


def test_highlight_endpoint_preserves_snapshot_and_validates_requests(client, saved_source):
    doc_id, _, version, source = saved_source
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    url = f'/documents/{doc_id}/reader.pdf?version={version}'
    response = client.get(url + '&highlight_page=1&q=summary&start=6&end=13')
    assert response.status_code == 200 and response.headers['content-type'] == 'application/pdf'
    assert source.read_bytes() != response.content
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert client.get(url).content == source.read_bytes()
    assert client.get(url + '&highlight_page=2&q=test').status_code == 422
    assert client.get(url + '&highlight_page=1&start=0&end=9999').status_code == 422
    assert client.get(url + '&start=0&end=1').status_code == 422
    assert client.get(url.replace(version, '0' * 64) + '&highlight_page=1&q=test').status_code == 409
    peer = {'Authorization': f"Bearer {create_access_token({'sub': '124'})}"}
    assert client.get(url + '&highlight_page=1&q=test', headers=peer).status_code == 403
