"""Export the saved comparison snapshot; never extract or regenerate AI output."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from pydantic import ValidationError
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.jobmode import JobMode
from app.models.jobstatus import JobStatus
from app.schemas.result import JobResultData


FONT_DIR = Path(__file__).resolve().parents[1] / 'assets' / 'fonts'
pdfmetrics.registerFont(TTFont('Comparison', str(FONT_DIR / 'NotoSans-Regular.ttf')))
pdfmetrics.registerFont(TTFont('ComparisonBold', str(FONT_DIR / 'NotoSans-Bold.ttf')))
FIELDS = (('value', 'Giá trị'), ('payment_term', 'Thanh toán'), ('penalty', 'Phạt'))
HEADERS = ('Tài liệu', 'Giá trị', 'Thanh toán', 'Phạt', 'Nguồn (trang)')


class IncompleteTable(ValueError):
    """A job cannot be exported as a complete comparison."""


def saved_table_rows(job):
    """Check every linked file, ownership and snapshot before emitting any bytes."""
    message = 'PDF export requires a completed job with a complete saved table.'
    files = sorted(job.job_files, key=lambda item: item.id)
    if (job.mode != JobMode.TABLE or job.status != JobStatus.COMPLETED or
            not 1 <= job.file_count <= 5 or job.completed_count != job.file_count or
            len(files) != job.file_count or len({f.document_id for f in files}) != len(files) or
            any(f.status != JobStatus.COMPLETED or not f.document or
                f.document.owner_id != job.owner_id for f in files)):
        raise IncompleteTable(message)
    try:
        result = JobResultData.model_validate(job.result_data)
        if set(result.documents) != {str(f.document_id) for f in files}:
            raise IncompleteTable(message)
        rows = []
        for file in files:
            row = result.documents[str(file.document_id)]
            raw_output = job.result_data['documents'][str(file.document_id)]['output']
            if (row.document_id != file.document_id or row.mode != 'table' or
                    row.analysis_status != 'completed' or row.output.type != 'table' or
                    not row.original_filename.strip() or
                    any(field not in raw_output for field, _ in FIELDS)):
                raise IncompleteTable(message)
            rows.append(row)
        return rows
    except (ValidationError, TypeError, KeyError) as error:
        raise IncompleteTable(message) from error


def render_table_pdf(job_id, rows, language='vi'):
    """A4 landscape, embedded Vietnamese fonts, wrapped cells and repeated headers."""
    en = language == 'en'
    fields = tuple(zip(('value', 'payment_term', 'penalty'), ('Value', 'Payment', 'Penalty'))) if en else FIELDS
    headers = ('Document', 'Value', 'Payment', 'Penalty', 'Sources (page)') if en else HEADERS
    heading_text = 'Financial clause comparison' if en else 'So sánh điều khoản tài chính'
    unverified_text = 'Unverified' if en else 'Chưa xác thực'
    body = ParagraphStyle('cell', fontName='Comparison', fontSize=9, leading=13,
                          splitLongWords=True, spaceAfter=3)
    heading = ParagraphStyle('header', parent=body, fontName='ComparisonBold',
                             textColor=colors.white)
    title = ParagraphStyle('title', parent=body, fontName='ComparisonBold',
                           fontSize=16, leading=22, spaceAfter=8)
    note = ParagraphStyle('note', parent=body, fontSize=8, leading=11,
                          textColor=colors.HexColor('#5b6472'))

    def paragraph(text, style=body):
        # Saved model text is plain text, never ReportLab XML or external links.
        return Paragraph(escape(text).replace('\n', '<br/>'), style)

    by_id = {row.document_id: row for row in rows}

    def sources_for(claim):
        # Only references into this authorized snapshot can become source pages.
        return [source for source in claim.evidence
                if (target := by_id.get(source.document_id)) and
                source.reader_version == target.reader.version and
                source.page <= target.reader.page_count and source.quote.strip()]

    data = [[paragraph(text, heading) for text in headers]]
    for row in rows:
        cells = [paragraph(row.original_filename)]
        sources_cell = []
        for field, label in fields:
            claim = getattr(row.output, field)
            has_text = bool(claim.text and claim.text.strip())
            sources = sources_for(claim) if has_text else []
            unverified = (claim.unverified or not sources or
                          len(sources) != len(claim.evidence) or bool(claim.verification_issues))
            cell = []
            if unverified:
                cell.append(paragraph('Unverified · Review required' if en else 'Chưa xác thực · Cần kiểm tra', note))
            cell.append(paragraph(claim.text if has_text else ('No information' if en else 'Không có thông tin')))
            cells.append(cell)
            sources_cell.append(paragraph(label + ':', note))
            if unverified:
                sources_cell.append(paragraph(unverified_text, note))
            for source in sources:
                target = by_id[source.document_id]
                kind = ('slide' if en else 'trang chiếu') if target.reader.page_kind == 'slide' else ('page' if en else 'trang')
                sources_cell.append(paragraph(f'{target.original_filename} — {kind} {source.page}', note))
            if not sources:
                sources_cell.append(paragraph('No verified source' if en else 'Chưa có nguồn xác thực', note))
        data.append(cells + [sources_cell])

    output = BytesIO()
    pdf = SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=14 * mm,
                            leftMargin=14 * mm, topMargin=14 * mm, bottomMargin=17 * mm,
                            title=f'{heading_text} — {job_id}',
                            author='Document workspace')
    widths = [pdf.width * fraction for fraction in (.18, .16, .24, .18, .24)]
    table = Table(data, colWidths=widths, repeatRows=1, splitByRow=1, splitInRow=1,
                  hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#243b53')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f6fa')]),
        ('GRID', (0, 0), (-1, -1), .4, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont('Comparison', 8)
        canvas.setFillColor(colors.HexColor('#5b6472'))
        canvas.drawString(14 * mm, 9 * mm, (f'Job {job_id} · {len(rows)} documents' if en else f'Tác vụ {job_id} · {len(rows)} tài liệu'))
        canvas.drawRightString(landscape(A4)[0] - 14 * mm, 9 * mm, f'{"Page" if en else "Trang"} {canvas.getPageNumber()}')
        canvas.restoreState()

    pdf.build([paragraph(heading_text, title),
               paragraph('Saved data · Unverified: check information against the original source.' if en else 'Dữ liệu đã lưu · Chưa xác thực: thông tin cần kiểm tra với tài liệu gốc.', note),
               Spacer(1, 5 * mm), table], onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
