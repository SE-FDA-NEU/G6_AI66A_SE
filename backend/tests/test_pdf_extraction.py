"""Real multipage, image-only and blank PDFs; no OCR or extraction mocks."""
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.models import Document, FileFormat
from app.services import pdf_extraction
from app.services.pdf_extraction import PDFExtractionError, extract_document_pdf, extract_pdf


def make_pdf(path, contents, rotation=0, cropbox=None):
    """Generate deterministic native PDF objects without an extra test dependency."""
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'']
    objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')
    objects.append(b'<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Length 3 >>\nstream\n\xff\x00\x00\nendstream')
    kids = []
    for content in contents:
        page_id = len(objects) + 1
        stream_id = page_id + 1
        kids.append(f'{page_id} 0 R')
        crop = f"/CropBox [{' '.join(map(str, cropbox))}]" if cropbox else ''
        objects.append((f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Rotate {rotation} {crop} '
                        f'/Resources << /Font << /F1 3 0 R >> /XObject << /Im0 4 0 R >> >> '
                        f'/Contents {stream_id} 0 R >>').encode())
        objects.append(f'<< /Length {len(content)} >>\nstream\n'.encode() + content + b'\nendstream')
    objects[1] = f"<< /Type /Pages /Count {len(kids)} /Kids [{' '.join(kids)}] >>".encode()
    pdf = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f'{i} 0 obj\n'.encode() + obj + b'\nendobj\n')
    xref = len(pdf)
    pdf.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        pdf.extend(f'{offset:010d} 00000 n \n'.encode())
    pdf.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    path.write_bytes(pdf)
    return path


@pytest.fixture
def multipage_pdf(tmp_path):
    return make_pdf(tmp_path / 'multipage.pdf', [
        b'BT /F1 12 Tf 72 720 Td (First page: contract 123.) Tj ET',
        b'q 100 0 0 100 72 600 cm /Im0 Do Q',  # Real raster image without a text layer.
        b'BT /F1 12 Tf 72 720 Td (Repeated words repeated.) Tj 0 -20 Td (Second line: 0.05% fee.) Tj ET',
        b'',  # Blank physical page.
    ])


def test_preserves_physical_pages_including_image_only_and_blank(multipage_pdf):
    result = extract_pdf(multipage_pdf)
    assert result['page_count'] == 4
    pages = result['extracted_text']
    assert [page['page'] for page in pages] == [1, 2, 3, 4]
    assert pages[0]['text'] == 'First page: contract 123.'
    assert pages[2]['text'] == 'Repeated words repeated.\nSecond line: 0.05% fee.'
    for i in (1, 3):
        assert pages[i]['text'] == '' and pages[i]['positions'] == []
    assert all(page['width'] == 612 and page['height'] == 792 for page in pages)
    with pdf_extraction.pdfplumber.open(multipage_pdf) as pdf:
        assert len(pdf.pages[1].images) == 1  # Fixture is not merely another blank page.
        assert pdf.pages[1].chars == []


def test_offsets_and_boxes_are_stable_and_match_stored_text(multipage_pdf):
    first = extract_pdf(multipage_pdf)
    assert extract_pdf(multipage_pdf) == first
    assert json.loads(json.dumps(first)) == first
    for page in first['extracted_text']:
        previous_end = 0
        for position in page['positions']:
            start, end = position['start'], position['end']
            assert previous_end <= start < end <= len(page['text'])
            assert page['text'][start:end] == position['text']
            x0, top, x1, bottom = position['bbox']
            assert 0 <= x0 < x1 <= page['width']
            assert 0 <= top < bottom <= page['height']
            previous_end = end
        covered = {i for p in page['positions'] for i in range(p['start'], p['end'])}
        assert all(i in covered for i, char in enumerate(page['text']) if not char.isspace())
    page = first['extracted_text'][2]
    offset = page['text'].index('Second')
    highlight = [p for p in page['positions'] if offset <= p['start'] < offset + len('Second')]
    assert ''.join(p['text'] for p in highlight) == 'Second'
    assert highlight[0]['bbox'][0] == pytest.approx(72)
    assert highlight[0]['bbox'][1] > page['positions'][0]['bbox'][1]


def test_rotated_page_geometry_and_number_are_preserved(tmp_path):
    path = make_pdf(tmp_path / 'rotated.pdf', [b'BT /F1 12 Tf 72 720 Td (Rotated source) Tj ET'], rotation=90)
    page = extract_pdf(path)['extracted_text'][0]
    assert page['page'] == 1 and page['rotation'] == 90
    assert (page['width'], page['height']) == (792, 612)
    assert page['positions'] and page['text']
    for position in page['positions']:
        assert page['text'][position['start']:position['end']] == position['text']
        x0, top, x1, bottom = position['bbox']
        assert 0 <= x0 < x1 <= 792 and 0 <= top < bottom <= 612


def test_accented_text_and_crop_geometry_are_not_normalized(tmp_path):
    path = make_pdf(tmp_path / 'accent.pdf', [b'BT /F1 12 Tf 72 720 Td (Caf\351 costs 10.05.) Tj ET'],
                    cropbox=(36, 36, 576, 756))
    page = extract_pdf(path)['extracted_text'][0]
    assert page['text'] == 'Café costs 10.05.'
    accented = next(p for p in page['positions'] if p['text'] == 'é')
    assert page['text'][accented['start']:accented['end']] == 'é'
    assert page['cropbox'] == [36, 36, 576, 756]
    assert page['page_bbox'] == [0, 0, 612, 792]
    assert page['positions'][0]['bbox'][0] == pytest.approx(72)


def save_document(session_factory, path, file_format=FileFormat.PDF):
    with session_factory() as db:
        doc = Document(owner_id=123, original_filename=path.name, storage_path=str(path),
                       file_format=file_format, file_size_bytes=path.stat().st_size,
                       page_count=1, extracted_text=[{'page': 1, 'text': 'old extraction'}],
                       expires_at=datetime.now() + timedelta(days=30))
        db.add(doc)
        db.commit()
        return doc.id


def test_persists_existing_structure_and_page_count(session_factory, multipage_pdf):
    document_id = save_document(session_factory, multipage_pdf)
    result = extract_document_pdf(document_id, session_factory)
    with session_factory() as db:
        doc = db.get(Document, document_id)
        assert doc.page_count == result['page_count'] == 4
        assert doc.extracted_text == result['extracted_text']
        assert [(p['page'], p['text']) for p in doc.extracted_text][1] == (2, '')
        assert doc.extracted_text[0]['positions']
    assert extract_document_pdf(document_id, session_factory) == result


def test_uploaded_document_metadata_exposes_persisted_page_count(client, session_factory, multipage_pdf):
    response = client.post('/upload', files=[('files', ('source.pdf', multipage_pdf.read_bytes(), 'application/pdf'))])
    assert response.status_code == 202
    job = client.get(f"/jobs/{response.json()['jobId']}").json()
    document_id = job['job_files'][0]['document_id']
    extract_document_pdf(document_id, session_factory)
    response = client.get(f'/documents/{document_id}')
    assert response.status_code == 200
    assert response.json()['page_count'] == 4
    assert 'extracted_text' not in response.json()  # Existing metadata API contract stays intact.


def test_invalid_pdf_leaves_previous_extraction_unchanged(session_factory, tmp_path):
    path = tmp_path / 'broken.pdf'
    path.write_bytes(b'not a PDF')
    document_id = save_document(session_factory, path)
    with pytest.raises(PDFExtractionError):
        extract_document_pdf(document_id, session_factory)
    with session_factory() as db:
        doc = db.get(Document, document_id)
        assert doc.page_count == 1
        assert doc.extracted_text == [{'page': 1, 'text': 'old extraction'}]


def test_commit_failure_keeps_metadata_atomic(session_factory, multipage_pdf, monkeypatch):
    document_id = save_document(session_factory, multipage_pdf)
    def fail_commit(_):
        raise SQLAlchemyError('simulated DB failure')
    monkeypatch.setattr(session_factory.class_, 'commit', fail_commit)
    with pytest.raises(SQLAlchemyError):
        extract_document_pdf(document_id, session_factory)
    with session_factory() as db:
        doc = db.get(Document, document_id)
        assert doc.page_count == 1
        assert doc.extracted_text == [{'page': 1, 'text': 'old extraction'}]


def test_missing_or_non_pdf_document_is_rejected(session_factory, multipage_pdf):
    with pytest.raises(LookupError):
        extract_document_pdf(999999, session_factory)
    document_id = save_document(session_factory, multipage_pdf, FileFormat.DOCX)
    with pytest.raises(ValueError, match='PDF document'):
        extract_document_pdf(document_id, session_factory)


def test_later_page_failure_does_not_persist_partial_text(session_factory, multipage_pdf, monkeypatch):
    document_id = save_document(session_factory, multipage_pdf)
    original = pdf_extraction._extract_page
    def fail_second(page):
        if page.page_number == 2:
            raise PDFExtractionError('Unreadable page')
        return original(page)
    monkeypatch.setattr(pdf_extraction, '_extract_page', fail_second)
    with pytest.raises(PDFExtractionError):
        extract_document_pdf(document_id, session_factory)
    with session_factory() as db:
        doc = db.get(Document, document_id)
        assert doc.page_count == 1
        assert doc.extracted_text == [{'page': 1, 'text': 'old extraction'}]
