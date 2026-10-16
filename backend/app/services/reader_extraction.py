"""Pin native extraction to the exact immutable PDF served by the reader.

DOCX pagination comes only from the rendered PDF. PPTX exports every slide,
including hidden slides, with no notes pages; its PDF page count must match
the presentation's slide list. Original files are never overwritten.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import zipfile
from xml.etree import ElementTree

from app.core.config import settings
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


def find_soffice():
    configured = settings.SOFFICE_BINARY
    candidates = [configured] if configured else [
        shutil.which('soffice'), shutil.which('libreoffice'),
        r'C:\Program Files\LibreOffice\program\soffice.com',
        r'C:\Program Files\LibreOffice\program\soffice.exe',
        '/Applications/LibreOffice.app/Contents/MacOS/soffice',
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise ReaderConversionError('converter_unavailable',
                                'LibreOffice is required. Install it or configure SOFFICE_BINARY.')


def _stop_conversion(process):
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.communicate()


def convert_office(source, file_format, output_dir):
    binary = find_soffice()
    options = {
        'ExportHiddenSlides': {'type': 'boolean', 'value': 'true'},
        'ExportNotesPages': {'type': 'boolean', 'value': 'false'},
        'ExportOnlyNotesPages': {'type': 'boolean', 'value': 'false'},
        'IsSkipEmptyPages': {'type': 'boolean', 'value': 'false'},
        'ExportFormFields': {'type': 'boolean', 'value': 'false'},
    }
    export_filter = 'writer_pdf_Export' if file_format == FileFormat.DOCX else 'impress_pdf_Export'
    profile = (output_dir / 'profile').resolve().as_uri()
    command = [binary, f'-env:UserInstallation={profile}', '--headless', '--norestore',
               '--nodefault', '--nolockcheck', '--convert-to',
               f'pdf:{export_filter}:{json.dumps(options, separators=(",", ":"))}',
               '--outdir', str(output_dir), str(source)]
    process_options = ({'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
                       if os.name == 'nt' else {'start_new_session': True})
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **process_options)
    except OSError as error:
        raise ReaderConversionError('converter_unavailable', 'Could not start LibreOffice.') from error
    try:
        process.communicate(timeout=settings.OFFICE_CONVERSION_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        _stop_conversion(process)
        raise ReaderConversionError('conversion_timed_out', 'Office to PDF conversion exceeded its time limit.') from error
    output = output_dir / f'{source.stem}.pdf'
    if process.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
        raise ReaderConversionError('conversion_failed', 'Office to PDF conversion did not produce a readable file.')
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
            document = db.get(Document, document_id)
            if document is None:
                raise LookupError('Document not found.')
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
            with tempfile.TemporaryDirectory(prefix='convert-', dir=output_root) as work:
                work = Path(work)
                snapshot = work / f'source.{document.file_format.value.lower()}'
                shutil.copyfile(source, snapshot)
                source_hash = sha256(snapshot)
                if document.file_format == FileFormat.PDF:
                    rendered = snapshot
                else:
                    rendered = converter(snapshot, document.file_format, work)
                try:
                    result = extract_pdf(rendered)
                except PDFExtractionError as error:
                    raise ReaderConversionError('invalid_rendered_pdf', 'The converted reader PDF could not be extracted.') from error
                if result['page_count'] == 0:
                    raise ReaderConversionError('empty_rendered_pdf', 'The converted PDF has no pages.')
                if document.file_format == FileFormat.PPTX and result['page_count'] != _slide_count(snapshot):
                    raise ReaderConversionError('slide_page_mismatch', 'PDF pages do not match the PPTX slides; source references cannot be trusted.')
                if sha256(source) != source_hash:
                    raise ReaderConversionError('source_changed', 'The source changed during conversion. Please retry.')
                digest = sha256(rendered)
                reference = {'sha256': digest, 'source_sha256': source_hash,
                             'page_kind': 'slide' if document.file_format == FileFormat.PPTX else 'page'}
                for page in result['extracted_text']:
                    page['reader'] = reference.copy()
                target = output_root / f'{digest}.pdf'
                if target.exists():
                    if sha256(target) != digest:
                        os.replace(rendered, target)  # Repair only with verified bytes for this exact hash.
                else:
                    os.replace(rendered, target)
                    created = target
                document.page_count = result['page_count']
                document.extracted_text = result['extracted_text']
                db.commit()
                return result
    except BaseException:
        if created is not None:
            created.unlink(missing_ok=True)
        raise
