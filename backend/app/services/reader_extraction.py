"""Pin native extraction to the exact immutable PDF served by the reader.

DOCX uses generated text-reader pages, not original Word pagination. PPTX exports every slide,
including hidden slides, with no notes pages; its PDF page count must match
the presentation's slide list. Original files are never overwritten.
"""
import hashlib
import os
from pathlib import Path
import re
import shutil
import tempfile
import zipfile
from app.services.document_retention import is_expired_source
from xml.etree import ElementTree

from app.models import Document, FileFormat
from app.services.pdf_extraction import extract_pdf, PDFExtractionError


class ReaderConversionError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(64 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def convert_office(source, file_format, output_dir):
    """Create the text reader PDF with Python libraries, no external app."""
    from app.services.office_reader import render_office_pdf
    try:
        output = render_office_pdf(source, file_format, output_dir)
    except Exception as error:
        raise ReaderConversionError('conversion_failed', 'Could not create a reader from this Office document.') from error
    if not output.is_file() or not output.stat().st_size:
        raise ReaderConversionError('conversion_failed', 'The Office reader PDF is empty or missing.')
    return output


def _slide_count(path):
    try:
        with zipfile.ZipFile(path) as archive:
            with archive.open('ppt/presentation.xml') as entry:
                data = entry.read(10 * 1024 * 1024 + 1)
        if len(data) > 10 * 1024 * 1024:
            raise ValueError('Presentation metadata too large')
        root = ElementTree.fromstring(data)
        return len(root.findall('./p:sldIdLst/p:sldId', {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, ElementTree.ParseError) as error:
        raise ReaderConversionError('invalid_presentation', 'Could not read the PPTX slide list.') from error


def reader_file(document, reference):
    version = reference.get('sha256', '')
    if not re.fullmatch(r'[0-9a-f]{64}', version):
        raise ReaderConversionError('invalid_reader_reference', 'The reader reference is invalid.')
    return Path(document.storage_path).parent / '.reader' / str(document.id) / f'{version}.pdf'


def reader_representation(document):
    pages = document.extracted_text
    if not isinstance(pages, list) or not pages or not isinstance(pages[0], dict) or not isinstance(pages[0].get('reader'), dict):
        raise ReaderConversionError('reader_not_ready', 'A stable reader PDF has not been prepared yet.')
    reference = pages[0]['reader']
    if (not re.fullmatch(r'[0-9a-f]{64}', reference.get('source_sha256', '')) or
            reference.get('page_kind') != ('slide' if document.file_format == FileFormat.PPTX else 'page')):
        raise ReaderConversionError('invalid_reader_reference', 'The reader source reference is invalid.')
    if (document.page_count != len(pages) or
            any(not isinstance(page, dict) or page.get('reader') != reference or page.get('page') != i
                for i, page in enumerate(pages, 1))):
        raise ReaderConversionError('invalid_reader_reference', 'Reader pages reference different files.')
    path = reader_file(document, reference)
    if not path.is_file() or sha256(path) != reference['sha256']:
        raise ReaderConversionError('reader_file_unavailable', 'The stored reader PDF is missing or changed. Prepare it again.')
    return path, reference


def prepare_reader(source, file_format, work, converter=None, on_page_count=None):
    """Prepare bytes and page metadata without touching the database.

    Both the manual reader endpoint and the cancellable job subprocess use
    this implementation. The caller owns the work directory and publication.
    """
    source, work = Path(source), Path(work)
    if not source.is_file():
        raise ReaderConversionError('source_missing', 'The original file is missing.')
    snapshot = work / f'source.{file_format.value.lower()}'
    shutil.copyfile(source, snapshot)
    source_hash = sha256(snapshot)
    rendered = snapshot if file_format == FileFormat.PDF else (converter or convert_office)(snapshot, file_format, work)
    try:
        result = extract_pdf(rendered, on_page_count=on_page_count) if on_page_count else extract_pdf(rendered)
    except PDFExtractionError as error:
        raise ReaderConversionError('invalid_rendered_pdf', f'The reader PDF could not be extracted: {error}') from error
    if not result['page_count']:
        raise ReaderConversionError('empty_rendered_pdf', 'The reader PDF has no pages.')
    if file_format == FileFormat.PPTX and result['page_count'] != _slide_count(snapshot):
        raise ReaderConversionError('slide_page_mismatch', 'PDF pages do not match the PPTX slides; source references cannot be trusted.')
    if sha256(source) != source_hash:
        raise ReaderConversionError('source_changed', 'The source changed during conversion. Please retry.')
    reference = {'sha256': sha256(rendered), 'source_sha256': source_hash,
                 'page_kind': 'slide' if file_format == FileFormat.PPTX else 'page'}
    if file_format != FileFormat.PDF:
        reference['renderer'] = 'python-text-v1'
    for page in result['extracted_text']:
        page['reader'] = reference.copy()
    return result, rendered


def publish_pdf(rendered, target):
    """Publish atomically even when the conversion temp directory is on C:
    and configured document storage is on a different volume.
    """
    with tempfile.NamedTemporaryFile(prefix='publish-', suffix='.pdf', dir=target.parent, delete=False) as handle:
        staged = Path(handle.name)
    try:
        shutil.copyfile(rendered, staged)
        os.replace(staged, target)
    finally:
        staged.unlink(missing_ok=True)


def extract_document_for_reader(document_id, session_factory, converter=None):
    """Store a PDF snapshot and its extracted pages in the existing JSON column.

    Page entries keep {page, text, positions, ...} and add a versioned reader
    reference. No schema migration is required. An unchanged source reuses
    its persisted representation, avoiding pagination drift after restarts.
    """
    converter = converter or convert_office
    created = None
    try:
        with session_factory() as db:
            document = db.query(Document).filter(Document.id == document_id).with_for_update().first()
            if document is None:
                raise LookupError('Document not found.')
            if is_expired_source(document):
                raise ReaderConversionError('source_expired', 'Source expired and is no longer available.')
            source = Path(document.storage_path)
            if not source.is_file():
                raise ReaderConversionError('source_missing', 'The original file is missing.')
            source_hash = sha256(source)
            try:
                _, reference = reader_representation(document)
                if reference['source_sha256'] == source_hash:
                    return {'page_count': document.page_count, 'extracted_text': document.extracted_text}
            except ReaderConversionError:
                pass
            output_root = source.parent / '.reader' / str(document.id)
            output_root.mkdir(parents=True, exist_ok=True)
            # Keep isolated temporary artifacts off the source storage path.
            with tempfile.TemporaryDirectory(prefix='documind-convert-') as work:
                work = Path(work)
                result, rendered = prepare_reader(source, document.file_format, work, converter)
                digest = result['extracted_text'][0]['reader']['sha256']
                target = output_root / f'{digest}.pdf'
                if target.exists():
                    if sha256(target) != digest:
                        publish_pdf(rendered, target)  # Repair only with verified bytes for this exact hash.
                else:
                    publish_pdf(rendered, target)
                    created = target
                document.page_count = result['page_count']
                document.extracted_text = result['extracted_text']
                db.commit()
                return result
    except BaseException:
        if created is not None:
            created.unlink(missing_ok=True)
        raise
