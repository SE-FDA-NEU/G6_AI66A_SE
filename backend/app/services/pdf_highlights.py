"""Draw search/citation highlights into a transient copy; source bytes stay intact."""
from io import BytesIO
import math

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas


def highlighted_pdf(path, page_data, *, query='', start=None, end=None):
    text = page_data['text']
    spans = []
    if query:
        # Preserve original Unicode code-point offsets when casefold expands a glyph.
        folded, offsets = [], []
        for index, char in enumerate(text):
            value = char.casefold()
            folded.append(value)
            offsets.extend([index] * len(value))
        haystack, needle = ''.join(folded), query.casefold()
        cursor = 0
        while needle and (found := haystack.find(needle, cursor)) >= 0:
            spans.append((offsets[found], offsets[found + len(needle) - 1] + 1))
            cursor = found + len(needle)
    if start is not None:
        if end is None or not 0 <= start < end <= len(text):
            raise ValueError('Highlight span is outside the page text.')
        spans.append((start, end))
    elif end is not None:
        raise ValueError('Highlight requires both start and end.')

    writer = PdfWriter(clone_from=path)
    page = writer.pages[page_data['page'] - 1]
    # pdfplumber stores rotation-adjusted, top-left coordinates. Normalize the
    # PDF content to that same visual orientation before drawing onto it.
    page.transfer_rotation_to_content()
    width, height = float(page.mediabox.width), float(page.mediabox.height)
    origin = page_data.get('page_bbox', [0, 0, width, height])
    overlay = BytesIO()
    canvas = Canvas(overlay, pagesize=(width, height))
    canvas.setBlendMode('Multiply')
    canvas.setFillAlpha(.38)
    merged = []
    for left, right in sorted(spans):
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
        else:
            merged.append((left, right))
    cursor = 0
    for position in sorted(page_data.get('positions', []), key=lambda item: item['start']):
        while cursor < len(merged) and merged[cursor][1] <= position['start']:
            cursor += 1
        if cursor == len(merged) or merged[cursor][0] >= position['end']:
            continue
        box = position.get('bbox')
        if not isinstance(box, list) or len(box) != 4 or not all(math.isfinite(v) for v in box):
            continue
        x0, top, x1, bottom = box
        if x1 <= x0 or bottom <= top:
            continue
        active = start is not None and position['start'] < end and position['end'] > start
        canvas.setFillColorRGB(*((1, .61, .12) if active else (1, .9, .1)))
        canvas.rect(x0 - origin[0], height - (bottom - origin[1]), x1 - x0, bottom - top, fill=1, stroke=0)
    canvas.showPage()
    canvas.save()
    page.merge_page(PdfReader(overlay).pages[0])
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
