"""Render the reviewed M5 Markdown as a PDF with fully bordered tables."""
from html import escape
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs' / 'M5-submission.md'
OUTPUT = ROOT / 'docs' / 'Team06_M5.pdf'
REPO_DOCS = 'https://github.com/SE-FDA-NEU/G6_AI66A_SE/blob/main/docs/'


def main():
    fonts = ROOT / 'backend' / 'app' / 'assets' / 'fonts'
    pdfmetrics.registerFont(TTFont('Noto', str(fonts / 'NotoSans-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('NotoBold', str(fonts / 'NotoSans-Bold.ttf')))
    pdfmetrics.registerFontFamily('Noto', normal='Noto', bold='NotoBold', italic='Noto', boldItalic='NotoBold')
    body = ParagraphStyle('Body', fontName='Noto', fontSize=9, leading=13, spaceAfter=8, splitLongWords=True)
    h1 = ParagraphStyle('H1', parent=body, fontName='NotoBold', fontSize=18, leading=24, spaceBefore=5, spaceAfter=15, keepWithNext=True)
    h2 = ParagraphStyle('H2', parent=body, fontName='NotoBold', fontSize=12, leading=17, spaceBefore=12, spaceAfter=8, keepWithNext=True)
    cell = ParagraphStyle('Cell', parent=body, fontSize=8.3, leading=11.5, spaceAfter=0)
    header = ParagraphStyle('TableHeader', parent=cell, fontName='NotoBold', textColor=colors.white)
    width = A4[0] - 72

    def inline(text):
        # Escape all source HTML; allow only Markdown's links, bold and inline code.
        text = re.sub(r'\\([_*`])', r'\1', text)
        links = []
        def link(match):
            label, target = match.groups()
            if not target.startswith(('https://', 'http://')):
                target = REPO_DOCS + target
            links.append(f'<link href="{escape(target, quote=True)}" color="#1a5b8f">{escape(label)}</link>')
            return f'LINKTOKEN{len(links)-1}ENDTOKEN'
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link, text)
        text = escape(text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'`([^`]+)`', r'<font color="#334155">\1</font>', text)
        for index, value in enumerate(links):
            text = text.replace(f'LINKTOKEN{index}ENDTOKEN', value)
        return text

    def table(rows):
        count = len(rows[0])
        if rows[0] == ['Field', 'Value']:
            widths = [133, width - 133]
        elif rows[0][0] == 'Item':
            widths = [90, 80, 150, width - 320]
        elif rows[0][0] == 'Area':
            widths = [85, 180, 125, width - 390]
        elif rows[0][0] == 'Signal':
            widths = [86, 342, width - 428]
        elif count == 3:
            widths = [width * .33, width * .38, width * .29]
        else:
            widths = [120, width - 120]
        cells = [[Paragraph(inline(value), header if index == 0 else cell) for value in row] for index, row in enumerate(rows)]
        result = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
        result.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), .6, colors.HexColor('#64748b')),
            ('BOX', (0, 0), (-1, -1), .85, colors.HexColor('#334155')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#253c52')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f5f8')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ]))
        return KeepTogether([result, Spacer(1, 10)])

    lines = SOURCE.read_text(encoding='utf-8').splitlines()
    assert lines[0].startswith('Running app: https://')
    story = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line == '---':
            story.append(PageBreak())
            index += 1
            continue
        if line.startswith('|'):
            rows = []
            while index < len(lines) and lines[index].strip().startswith('|'):
                values = [value.strip() for value in lines[index].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[-: ]+', value) for value in values):
                    rows.append(values)
                index += 1
            story.append(table(rows))
            continue
        if line.startswith('# '):
            story.append(Paragraph(inline(line[2:]), h1))
            index += 1
            continue
        if line.startswith('## '):
            if line.startswith(('## 4.', '## 6.')):
                story.append(PageBreak())
            story.append(Paragraph(inline(line[3:]), h2))
            index += 1
            continue
        paragraph = [line]
        index += 1
        while index < len(lines) and lines[index].strip() and not lines[index].startswith(('#', '|', '---')):
            paragraph.append(lines[index].strip())
            index += 1
        story.append(Paragraph(inline(' '.join(paragraph)), body))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Noto', 8)
        canvas.setFillColor(colors.HexColor('#526173'))
        canvas.drawString(36, 23, 'Team 06 — DocuMind | Milestone 5')
        canvas.drawRightString(A4[0]-36, 23, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=36, rightMargin=36,
                           topMargin=32, bottomMargin=42, title='Team06 M5 — DocuMind', author='Team 06')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == '__main__':
    main()
