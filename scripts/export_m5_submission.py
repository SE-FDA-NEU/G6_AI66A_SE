"""Export the M5 submission block and workflow with closed, fully ruled tables."""
from html import escape
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs' / 'M5-submission.md'
OUTPUT = ROOT / 'docs' / 'Team06_M5.pdf'


def read_table(text, heading):
    section = text.split(heading, 1)[1].split('\n## ', 1)[0]
    rows = [line.strip().strip('|').split('|') for line in section.splitlines() if line.startswith('|')]
    return [[cell.strip() for cell in row] for row in rows if not all(re.fullmatch(r'[-: ]+', cell) for cell in row)]


def main():
    text = SOURCE.read_text(encoding='utf-8')
    fonts = ROOT / 'backend' / 'app' / 'assets' / 'fonts'
    pdfmetrics.registerFont(TTFont('Noto', str(fonts / 'NotoSans-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('NotoBold', str(fonts / 'NotoSans-Bold.ttf')))
    draft = 'PENDING' in text or '**Draft' in text
    body = ParagraphStyle('Body', fontName='Noto', fontSize=9, leading=13, alignment=TA_LEFT, splitLongWords=True)
    heading = ParagraphStyle('Heading', parent=body, fontName='NotoBold', fontSize=17, leading=23, spaceAfter=16)
    small = ParagraphStyle('Small', parent=body, fontSize=8, leading=12)
    header = ParagraphStyle('Header', parent=body, fontName='NotoBold', textColor=colors.white)

    def paragraph(value, style=body):
        # Link whole URLs while allowing long repository/run paths to wrap in cells.
        chunks = re.split(r'(https://[^\s]+)', value)
        markup = ''.join(f'<link href="{escape(part, quote=True)}" color="#195b92">{escape(part)}</link>'
                         if part.startswith('https://') else escape(part) for part in chunks)
        return Paragraph(markup, style)

    def table(rows, widths):
        cells = [[paragraph(cell, header if index == 0 else body) for cell in row] for index, row in enumerate(rows)]
        result = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
        result.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.65, colors.HexColor('#546578')),
            ('BOX', (0, 0), (-1, -1), 0.9, colors.HexColor('#334155')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#253c52')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f5f8')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 9),
            ('RIGHTPADDING', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        return result

    width = A4[0] - 72
    first_line = text.splitlines()[0]
    assert first_line.startswith('Running app: https://')
    block = read_table(text, '## 7. What to submit here')
    workflow = read_table(text, '## 6. Submission workflow')
    assert len(block) == 9 and len(workflow) == 7
    story = [paragraph(first_line), Spacer(1, 18), paragraph('Team 06 — Milestone 5 submission', heading)]
    if draft:
        story.extend([paragraph('DRAFT — release acceptance and final submission fields are pending.', small), Spacer(1, 12)])
    story.extend([table(block, [137, width - 137]), Spacer(1, 14),
                  paragraph('Submit one file: Team06_M5.pdf. No LMS upload has been performed.', small),
                  PageBreak(), paragraph('6. Submission workflow', heading),
                  table(workflow, [68, 192, width - 260]), Spacer(1, 12),
                  paragraph('Use Review changes for the formal review. Resolve pending items before uploading the final PDF.', small)])

    def footer(canvas, doc):
        canvas.setFont('Noto', 8)
        canvas.setFillColor(colors.HexColor('#526173'))
        canvas.drawString(36, 23, 'Team 06 — DocuMind' + (' | DRAFT — not ready for LMS' if draft else ''))
        canvas.drawRightString(A4[0] - 36, 23, str(doc.page))

    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=36, rightMargin=36,
                           topMargin=32, bottomMargin=42, title='Team 06 — Milestone 5 submission', author='Team 06 — DocuMind')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == '__main__':
    main()
