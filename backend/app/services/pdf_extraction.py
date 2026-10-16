"""Extract a native PDF text layer without OCR or placeholder text.

Each entry retains the physical one-based page number and existing `text`
field. `positions` contains glyph text, half-open Unicode code-point offsets
into that exact page text, and [x0, top, x1, bottom] bounding boxes in PDF
points. Coordinates increase right/down in pdfplumber's un-cropped,
rotation-adjusted page space. Use page_bbox/cropbox to map into a viewport.
Layout whitespace without a source glyph has no invented bounding box.
"""
from pathlib import Path

import pdfplumber

from app.models import Document, FileFormat


class PDFExtractionError(ValueError):
    """Extraction failed instead of returning incomplete or fabricated text."""


def _box(values):
    return [round(float(value), 6) for value in values]


def _extract_page(page):
    lines = page.extract_text_lines(layout=False, return_chars=True, expand_ligatures=False)
    text_parts = []
    positions = []
    offset = 0
    for line in lines:
        text = line['text']
        if not text:
            continue
        if text_parts:
            offset += 1  # Newline between extracted lines.
        text_parts.append(text)
        cursor = 0
        for char in line['chars']:
            value = char['text']
            if not value:
                continue
            start = text.find(value, cursor)
            if start < 0:
                raise PDFExtractionError('PDF text could not be mapped to source positions.')
            end = start + len(value)
            positions.append({
                'start': offset + start, 'end': offset + end, 'text': value,
                'bbox': _box((char['x0'], char['top'], char['x1'], char['bottom'])),
            })
            cursor = end
        offset += len(text)
    return {
        'page': page.page_number,
        'text': '\n'.join(text_parts),
        'positions': positions,
        'width': float(page.width), 'height': float(page.height),
        'page_bbox': _box(page.bbox),
        'cropbox': _box(page.cropbox) if page.cropbox else None,
        'rotation': page.rotation,
        'coordinate_system': 'top-left',
        'offset_unit': 'unicode_codepoint',
    }


def extract_pdf(path: str | Path) -> dict:
    """Return {page_count, extracted_text: [{page, text, positions, ...}]}.

    Blank, graphics-only and image-only pages remain present with text=""
    and positions=[]. Parse errors fail the entire extraction. No OCR,
    summarization, normalizing of source words, or replacement text is used.
    """
    try:
        with pdfplumber.open(path) as pdf:
            pages = []
            for page in pdf.pages:
                try:
                    pages.append(_extract_page(page))
                finally:
                    page.close()
            return {'page_count': len(pages), 'extracted_text': pages}
    except PDFExtractionError:
        raise
    except Exception as error:
        raise PDFExtractionError('Could not extract native text from this PDF.') from error


def extract_document_pdf(document_id: int, session_factory) -> dict:
    """Persist both existing fields atomically using a private DB session.

    Internal worker service, not an unauthenticated HTTP endpoint. API callers
    must check ownership before invoking it. All pages must be extracted
    successfully before either database field is changed.
    """
    with session_factory() as db:
        document = db.get(Document, document_id)
        if document is None:
            raise LookupError('Document not found.')
        if document.file_format != FileFormat.PDF:
            raise ValueError('PDF extraction requires a PDF document.')
        result = extract_pdf(document.storage_path)
        document.page_count = result['page_count']
        document.extracted_text = result['extracted_text']
        db.commit()
        return result
