"""Render PPTX with its slide layout; build DOCX text-reader pages in Python.

DOCX pages are generated reader pages, not a reconstruction of Word's layout.
PPTX uses LibreOffice PDF export, including blank/hidden slides, without notes.
Evidence is subsequently extracted from these exact PDF bytes.
"""
from pathlib import Path
import threading
import json
import shutil
import subprocess

from xml.sax.saxutils import escape

from app.core.config import settings

from docx import Document as WordDocument
from docx.oxml.ns import qn
from docx.table import Table as WordTable
from reportlab import rl_config
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from app.models import FileFormat

_font_lock = threading.Lock()


def reader_font():
    name = 'DocuMindOfficeReader'
    with _font_lock:
        if name not in pdfmetrics.getRegisteredFontNames():
            candidates = [Path('/System/Library/Fonts/Supplemental/Arial.ttf'),
                          Path('C:/Windows/Fonts/arial.ttf'),
                          Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
            candidates.extend(Path(folder) / 'Vera.ttf' for folder in rl_config.TTFSearchPath)
            for path in candidates:
                if path.is_file():
                    pdfmetrics.registerFont(TTFont(name, str(path)))
                    break
            else:
                raise ValueError('No Unicode reader font is available.')
    return name


def _paragraph(text, style):
    return Paragraph(escape(text).replace('\n', '<br/>').replace('\t', '    '), style)


def _paragraph_parts(paragraph):
    """Keep explicit page breaks and hyperlink text in original XML order."""
    pieces = []
    for element in paragraph._p.iter():
        if element.tag == qn('w:t'):
            pieces.append(element.text or '')
        elif element.tag == qn('w:tab'):
            pieces.append('\t')
        elif element.tag in (qn('w:br'), qn('w:cr')):
            if element.get(qn('w:type')) == 'page':
                yield ''.join(pieces)
                yield None
                pieces = []
            else:
                pieces.append('\n')
    yield ''.join(pieces)


def _render_docx(source, output):
    document = WordDocument(source)
    section = document.sections[0]
    width = section.page_width.pt if section.page_width else 595.28
    height = section.page_height.pt if section.page_height else 841.89
    left = min(section.left_margin.pt if section.left_margin else 54, width / 4)
    right = min(section.right_margin.pt if section.right_margin else 54, width / 4)
    top = min(section.top_margin.pt if section.top_margin else 54, height / 4)
    bottom = min(section.bottom_margin.pt if section.bottom_margin else 54, height / 4)
    font = reader_font()
    style = ParagraphStyle('OfficeBody', fontName=font, fontSize=11, leading=15,
                           spaceAfter=6, splitLongWords=True)
    table_style = ParagraphStyle('OfficeCell', parent=style, fontSize=9, leading=12, spaceAfter=2)
    story = []
    for block in document.iter_inner_content():
        if isinstance(block, WordTable):
            rows, seen = [], set()
            for row in block.rows:
                cells = []
                for cell in row.cells:
                    # Merged cells can appear repeatedly in the row/cell list.
                    text = '' if cell._tc in seen else cell.text
                    seen.add(cell._tc)
                    cells.append(_paragraph(text, table_style))
                rows.append(cells)
            if rows and rows[0]:
                columns = max(map(len, rows))
                rows = [row + [''] * (columns - len(row)) for row in rows]
                story.append(LongTable(rows, colWidths=[(width-left-right-12)/columns]*columns,
                                       splitByRow=1, splitInRow=1, style=[
                                           ('VALIGN', (0,0), (-1,-1), 'TOP'),
                                           ('GRID', (0,0), (-1,-1), .4, '#cccccc')]))
                story.append(Spacer(1,6))
            continue
        if block.paragraph_format.page_break_before:
            story.append(PageBreak())
        for text in _paragraph_parts(block):
            if text is None:
                story.append(PageBreak())
            elif text:
                story.append(_paragraph(text, style))
    if not story:
        story.append(Spacer(1,1))
    SimpleDocTemplate(str(output), pagesize=(width,height), leftMargin=left,
                      rightMargin=right, topMargin=top, bottomMargin=bottom).build(story)


def soffice_binary():
    if settings.SOFFICE_BINARY:
        configured = Path(settings.SOFFICE_BINARY).expanduser()
        if configured.is_file():
            return str(configured)
        found = shutil.which(settings.SOFFICE_BINARY)
        if found:
            return found
        raise FileNotFoundError('Configured LibreOffice executable is missing.')
    found = shutil.which('soffice') or shutil.which('libreoffice')
    if found:
        return found
    candidates = [Path('/Applications/LibreOffice.app/Contents/MacOS/soffice'),
                  Path('C:/Program Files/LibreOffice/program/soffice.exe')]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError('Install LibreOffice on the backend or set SOFFICE_BINARY.')


def _render_pptx(source, output):
    # A separate profile prevents concurrent conversions from connecting to an
    # existing GUI process. The caller supplies a private temporary directory.
    output = Path(output).resolve()
    source = Path(source).resolve()
    profile = output.parent / 'libreoffice-profile'
    options = {name: {'type': 'boolean', 'value': value} for name, value in {
        'ExportHiddenSlides': 'true', 'ExportNotesPages': 'false',
        'ExportOnlyNotesPages': 'false', 'ExportNotes': 'false',
    }.items()}
    command = [soffice_binary(), '-env:UserInstallation=' + profile.as_uri(),
               '--headless', '--nologo', '--nodefault', '--norestore',
               '--convert-to', 'pdf:impress_pdf_Export:' + json.dumps(options, separators=(',', ':')),
               '--outdir', str(output.parent), str(source)]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        # The cancellable job's BR deadline can interrupt this earlier.
        process.wait(timeout=90)
        generated = output.parent / (source.stem + '.pdf')
        if process.returncode or not generated.is_file() or not generated.stat().st_size:
            raise ValueError('LibreOffice did not produce a slide PDF.')
        if generated != output:
            generated.replace(output)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def render_office_pdf(source, file_format, output_dir):
    output = Path(output_dir) / 'office-reader.pdf'
    if file_format == FileFormat.DOCX:
        _render_docx(source, output)
    elif file_format == FileFormat.PPTX:
        _render_pptx(source, output)
    else:
        raise ValueError('Unsupported Office format.')
    return output
