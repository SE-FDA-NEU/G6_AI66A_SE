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
