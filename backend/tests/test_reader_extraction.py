import hashlib
import subprocess
from datetime import datetime, timedelta

import pytest
from docx import Document as WordDocument
from pptx import Presentation
from pptx.util import Inches
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.security import create_access_token
from app.models import Document, FileFormat
from app.services import reader_extraction as reader
from app.services.pdf_extraction import extract_pdf
from test_pdf_extraction import make_pdf


@pytest.fixture
def sources(tmp_path):
    word = WordDocument()
    word.add_paragraph('DOCX page one alpha')
    word.add_paragraph('DOCX page one beta')
    word.add_page_break()
    word.add_paragraph('DOCX page two gamma')
    word.add_paragraph('DOCX page two delta')
    docx = tmp_path / 'source.docx'
    word.save(docx)
    slides = Presentation()
    for i in range(3):
        slide = slides.slides.add_slide(slides.slide_layouts[6])
        if i < 2:
            slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(1)).text = f'PPTX slide {i + 1}'
        if i == 1:
            slide._element.set('show', '0')
        slide.notes_slide.notes_text_frame.text = 'SPEAKER NOTES MUST NOT BECOME READER PAGES'
    pptx = tmp_path / 'source.pptx'
    slides.save(pptx)
    return {FileFormat.DOCX: docx, FileFormat.PPTX: pptx}


def save_document(factory, source, fmt):
    with factory() as db:
        document = Document(owner_id=123, original_filename=source.name, storage_path=str(source),
                            file_format=fmt, file_size_bytes=source.stat().st_size,
                            expires_at=datetime.now() + timedelta(days=30))
        db.add(document)
        db.commit()
        return document.id


def fake_converter(source, fmt, output_dir):
    # Tests conversion/storage failure paths independently of LibreOffice installation.
    texts = ['DOCX page one alpha DOCX page one beta', 'DOCX page two gamma DOCX page two delta'] if fmt == FileFormat.DOCX else ['PPTX slide 1', 'PPTX slide 2', '']
    return make_pdf(output_dir / 'source.pdf', [
        f'BT /F1 12 Tf 72 720 Td ({text}) Tj ET'.encode() if text else b'' for text in texts
    ])


def assert_reader_matches_api(client, document_id, result, tmp_path):
    response = client.get(f'/documents/{document_id}/pages')
    assert response.status_code == 200
    metadata = response.json()
    file_response = client.get(metadata['reader_url'])
    assert file_response.status_code == 200
    assert file_response.headers['content-type'] == 'application/pdf'
    assert file_response.headers['x-reader-version'] == metadata['reader_version']
    assert hashlib.sha256(file_response.content).hexdigest() == metadata['reader_version']
    displayed = tmp_path / 'actually-displayed.pdf'
    displayed.write_bytes(file_response.content)
    displayed_pages = extract_pdf(displayed)['extracted_text']
    assert metadata['page_count'] == result['page_count'] == len(displayed_pages)
    for extracted, shown in zip(metadata['pages'], displayed_pages):
        assert extracted['page'] == shown['page']
        assert extracted['text'] == shown['text']
        assert extracted['positions'] == shown['positions']
        assert extracted['reader']['sha256'] == metadata['reader_version']
    return metadata, file_response.content


@pytest.mark.parametrize('fmt', [FileFormat.DOCX, FileFormat.PPTX])
def test_persisted_pages_are_extracted_from_the_exact_reader_file(client, session_factory, sources, fmt, tmp_path):
    document_id = save_document(session_factory, sources[fmt], fmt)
    calls = []
    def convert(*args):
        calls.append(1)
        return fake_converter(*args)
    result = reader.extract_document_for_reader(document_id, session_factory, convert)
    expected_pages = 2 if fmt == FileFormat.DOCX else 3
    assert result['page_count'] == expected_pages
    metadata, displayed = assert_reader_matches_api(client, document_id, result, tmp_path)
    assert metadata['page_kind'] == ('slide' if fmt == FileFormat.PPTX else 'page')
    assert [p['page'] for p in result['extracted_text']] == list(range(1, expected_pages + 1))
    if fmt == FileFormat.PPTX:
        assert result['extracted_text'][2]['text'] == ''
    else:
        assert len(WordDocument(sources[fmt]).paragraphs) > expected_pages
    assert reader.extract_document_for_reader(document_id, session_factory, convert) == result
    assert len(calls) == 1  # No re-pagination or conversion on a revisit.
    assert client.get(metadata['reader_url']).content == displayed
    assert client.get(f'/documents/{document_id}/reader.pdf?version=wrong').status_code == 409


def test_conversion_failure_does_not_overwrite_an_existing_reader(client, session_factory, sources):
    source = sources[FileFormat.DOCX]
    document_id = save_document(session_factory, source, FileFormat.DOCX)
    old = reader.extract_document_for_reader(document_id, session_factory, fake_converter)
    old_url = client.get(f'/documents/{document_id}/pages').json()['reader_url']
    old_bytes = client.get(old_url).content
    doc = WordDocument(source)
    doc.add_paragraph('source changed')
    doc.save(source)
    def failing(*_):
        raise reader.ReaderConversionError('conversion_failed', 'Conversion failed explicitly')
    with pytest.raises(reader.ReaderConversionError, match='explicitly'):
        reader.extract_document_for_reader(document_id, session_factory, failing)
    assert client.get(old_url).content == old_bytes
    with session_factory() as db:
        assert db.get(Document, document_id).extracted_text == old['extracted_text']


def test_pptx_page_count_mismatch_is_explicit_and_saves_no_metadata(session_factory, sources):
    document_id = save_document(session_factory, sources[FileFormat.PPTX], FileFormat.PPTX)
    def wrong(source, fmt, output):
        return make_pdf(output / 'source.pdf', [b''])
    with pytest.raises(reader.ReaderConversionError) as error:
        reader.extract_document_for_reader(document_id, session_factory, wrong)
    assert error.value.code == 'slide_page_mismatch'
    with session_factory() as db:
        assert db.get(Document, document_id).page_count is None
        assert db.get(Document, document_id).extracted_text is None


def test_invalid_converted_pdf_and_commit_failure_clean_new_artifacts(session_factory, sources, monkeypatch):
    document_id = save_document(session_factory, sources[FileFormat.DOCX], FileFormat.DOCX)
    def invalid(source, fmt, output):
        path = output / 'invalid.pdf'
        path.write_bytes(b'not PDF')
        return path
    with pytest.raises(reader.ReaderConversionError) as error:
        reader.extract_document_for_reader(document_id, session_factory, invalid)
    assert error.value.code == 'invalid_rendered_pdf'
    def fail_commit(_):
        raise SQLAlchemyError('test DB failure')
    monkeypatch.setattr(session_factory.class_, 'commit', fail_commit)
    with pytest.raises(SQLAlchemyError):
        reader.extract_document_for_reader(document_id, session_factory, fake_converter)
    assert not list((sources[FileFormat.DOCX].parent / '.reader').rglob('*.pdf'))
    with session_factory() as db:
        assert db.get(Document, document_id).extracted_text is None


@pytest.mark.parametrize('suffix', ['pages', 'reader.pdf?version=' + '0' * 64])
def test_reader_authorization_precedes_file_access(client, session_factory, sources, suffix):
    document_id = save_document(session_factory, sources[FileFormat.DOCX], FileFormat.DOCX)
    other = f"Bearer {create_access_token({'sub': '124'})}"
    assert client.get(f'/documents/{document_id}/{suffix}', headers={'Authorization': other}).status_code == 403
    client.headers.pop('Authorization')
    assert client.get(f'/documents/{document_id}/{suffix}').status_code == 401


def test_prepare_endpoint_reports_missing_converter_and_cannot_fallback_to_paragraphs(client, session_factory, sources, monkeypatch):
    document_id = save_document(session_factory, sources[FileFormat.DOCX], FileFormat.DOCX)
    monkeypatch.setattr(settings, 'SOFFICE_BINARY', '/no/such/soffice')
    response = client.post(f'/documents/{document_id}/reader')
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'converter_unavailable'
    assert client.get(f'/documents/{document_id}/pages').status_code == 409
    with session_factory() as db:
        assert db.get(Document, document_id).page_count is None


def test_tampered_reader_pdf_is_not_served(client, session_factory, sources):
    document_id = save_document(session_factory, sources[FileFormat.DOCX], FileFormat.DOCX)
    reader.extract_document_for_reader(document_id, session_factory, fake_converter)
    url = client.get(f'/documents/{document_id}/pages').json()['reader_url']
    with session_factory() as db:
        path, _ = reader.reader_representation(db.get(Document, document_id))
    path.write_bytes(b'different file')
    assert client.get(url).status_code == 409
    reader.extract_document_for_reader(document_id, session_factory, fake_converter)
    assert client.get(url).status_code == 200


@pytest.mark.parametrize('returncode', [0, 1])
def test_missing_converter_output_is_failure_even_with_zero_exit_code(tmp_path, monkeypatch, returncode):
    monkeypatch.setattr(reader, 'find_soffice', lambda: 'test-soffice')
    class FakeProcess:
        def communicate(self, timeout):
            return b'', b''
    process = FakeProcess()
    process.returncode = returncode
    monkeypatch.setattr(reader.subprocess, 'Popen', lambda *a, **k: process)
    with pytest.raises(reader.ReaderConversionError) as error:
        reader.convert_office(tmp_path / 'broken.docx', FileFormat.DOCX, tmp_path)
    assert error.value.code == 'conversion_failed'


def test_conversion_process_timeout_is_explicit_and_stops_the_process(tmp_path, monkeypatch):
    monkeypatch.setattr(reader, 'find_soffice', lambda: 'test-soffice')
    class FakeProcess:
        def communicate(self, timeout):
            raise subprocess.TimeoutExpired('test', timeout)
    stopped = []
    process = FakeProcess()
    monkeypatch.setattr(reader.subprocess, 'Popen', lambda *a, **k: process)
    monkeypatch.setattr(reader, '_stop_conversion', lambda child: stopped.append(child))
    with pytest.raises(reader.ReaderConversionError) as error:
        reader.convert_office(tmp_path / 'source.docx', FileFormat.DOCX, tmp_path)
    assert error.value.code == 'conversion_timed_out'
    assert stopped == [process]


@pytest.mark.parametrize('fmt', [FileFormat.DOCX, FileFormat.PPTX])
def test_real_libreoffice_source_pages_match_displayed_reader(client, session_factory, sources, fmt, tmp_path):
    try:
        reader.find_soffice()
    except reader.ReaderConversionError:
        pytest.skip('Install LibreOffice or set SOFFICE_BINARY to run the real converter integration test')
    document_id = save_document(session_factory, sources[fmt], fmt)
    response = client.post(f'/documents/{document_id}/reader')
    assert response.status_code == 200, response.text
    with session_factory() as db:
        doc = db.get(Document, document_id)
        result = {'page_count': doc.page_count, 'extracted_text': doc.extracted_text}
    metadata, _ = assert_reader_matches_api(client, document_id, result, tmp_path)
    texts = [page['text'] for page in metadata['pages']]
    if fmt == FileFormat.DOCX:
        assert len(texts) == 2
        assert 'page one alpha' in texts[0] and 'page one beta' in texts[0]
        assert 'page two gamma' in texts[1] and 'page two delta' in texts[1]
        assert len(WordDocument(sources[fmt]).paragraphs) != len(texts)
    else:
        assert len(texts) == 3
        assert 'PPTX slide 1' in texts[0]
        assert 'PPTX slide 2' in texts[1]  # Hidden slide retains physical slide number 2.
        assert texts[2] == ''
        assert all('SPEAKER NOTES' not in text for text in texts)
