"""Offline, synthetic acceptance sources and controlled provider outputs for T145.

Generate: python test/acceptance_fixtures.py
Local opt-in seed: python src/init_db.py --acceptance
Never calls a model. Expected quotes refer to extracted physical PDF pages.
"""
import argparse
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURES = ROOT / 'test' / 'fixtures' / 'acceptance'
AMOUNTS = ['1,200,000,000 VND', '2,500,000,000 VND', '999,999.99 USD',
           '0.00 VND', '750,000,000 VND']


def definitions():
    documents = []
    for number, amount in enumerate(AMOUNTS, 1):
        fields = {'value': amount, 'payment_term': 'Within 30 days' if number < 5 else None,
                  'penalty': '0.05% per day'}
        pages = [f'Contract {number}. Synthetic acceptance data.\nContract value: {amount}',
                 'Payment term: Within 30 days' if number < 5 else 'No payment schedule provided.',
                 'Penalty: 0.05% per day']
        documents.append({'key': f'contract-{number}', 'pages': pages, 'fields': fields,
                          'confidence': 79 if number == 1 else 80 if number == 2 else 90})
    documents.append({'key': 'report-15-pages', 'pages': [
        'Market report. Revenue is 1,200,000,000 VND.',
        'Recommended action: Review the revenue forecast before approving the budget.',
        'Recommended action: Compare supplier quotations before renewing the supply contract.',
        'Late payment incurs a penalty of 0.05% per day.',
        'Market demand remains stable.',
        'Orchid liquidity covenant requires a quarterly cash reserve review.',
        *[f'Report section {page}. Demand observations for period {page}.' for page in range(7, 16)]],
        'actions': [2, 3]})
    documents.append({'key': 'contract-24-pages', 'pages': [
        'Amber escrow release requires signed delivery acceptance.' if page == 12 else
        f'Contract annex page {page}. Administrative contact details only.' for page in range(1, 25)]})
    documents.append({'key': 'textless-page', 'pages': ['']})
    documents.append({'key': 'insufficient-actions', 'pages': [
        'Archive report. Revenue was 750,000,000 VND.',
        'Recommended action: Retain the signed receipt.'], 'actions': [2],
        'limitation': 'The source supports only one recommended action; a second action is unsupported.'})
    documents.append({'key': 'missing-evidence', 'pages': ['The contract identifies the parties only.'],
                      'unsupported': 'The contract guarantees a 99% return.'})
    for number in range(1, 11):
        documents.append({'key': f'course-note-{number:02}', 'pages': [
            f'Course note {number}. ' + ('Macroeconomics studies aggregate demand.' if number <= 8
                                      else 'Microeconomics studies household choices.')],
            'ai_label': 'Macroeconomics' if number <= 8 else 'Microeconomics',
            'user_label': 'User correction' if number <= 8 else 'Macroeconomics'})
    for index, document in enumerate(documents):
        document.update(filename=document['key'] + '.pdf',
                        folder=['Economics 101', 'Research', None][index % 3])
    return documents


def write_pdf(path, pages):
    from reportlab.pdfgen.canvas import Canvas
    canvas = Canvas(str(path), invariant=1, pageCompression=0)
    canvas.setTitle(path.stem + ' (synthetic acceptance fixture)')
    for text in pages:
        if text:
            for line, value in enumerate(text.splitlines()):
                canvas.drawString(36, 780 - line * 20, value)
        else:
            # A physical graphics-only page, deliberately without a text layer.
            canvas.rect(60, 600, 180, 80, fill=1)
        canvas.showPage()
    canvas.save()


def build(destination=FIXTURES):
    from app.services.pdf_extraction import extract_pdf
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    answers = {'schema_version': 1, 'synthetic': True, 'documents': [],
               'account': {'document_count': 20, 'ai_label': 'Macroeconomics', 'ai_label_count': 8},
               'search': [
                   {'query': 'Orchid liquidity covenant', 'hits': [{'key': 'report-15-pages', 'page': 6}]},
                   {'query': 'Amber escrow release', 'hits': [{'key': 'contract-24-pages', 'page': 12}]},
                   {'query': 'volcanic submarine zirconium', 'hits': []}],
               'manual_checks': [
                   'Compare all five financial rows with their original PDF pages; preserve commas, currencies and daily units.',
                   'Open each citation and compare the quote with the source, not merely the generated answer.',
                   'Verify page 6 and page 12 navigation after refreshing the reader.',
                   'Graphics-only page must not produce invented text, facts or source links.',
                   'Missing evidence must show Unverified and no fabricated link.',
                   'One supported action must retain an explicit limitation; do not invent a second action.',
                   '79% is low; 80% is high; neither is a user confirmation.',
                   '20 documents, 8 exact AI-label matches regardless of folder; clear filter restores 20.',
                   'Real model wording/ranking is reviewed against source; controlled outputs are not a real-model benchmark.']}
    for spec in definitions():
        path = destination / spec['filename']
        write_pdf(path, spec['pages'])
        extracted = extract_pdf(path)
        entry = {key: value for key, value in spec.items() if key != 'pages'}
        entry.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                     page_count=extracted['page_count'], pages=[])
        for page in extracted['extracted_text']:
            entry['pages'].append({'page': page['page'], 'text': page['text']})
        entry['expected_label'] = {
            'ai_label': spec.get('ai_label', 'Contract'),
            'ai_confidence': spec.get('confidence', 90) / 100,
            'confidence_level': 'low' if spec.get('confidence', 90) < 80 else 'high',
            'review_state': 'needs_review', 'user_label': spec.get('user_label')}
        if 'fields' in spec:
            entry['field_evidence'] = {}
            for field, value in spec['fields'].items():
                page_number = {'value': 1, 'payment_term': 2, 'penalty': 3}[field]
                text = entry['pages'][page_number - 1]['text']
                start = text.index(value) if value is not None else None
                entry['field_evidence'][field] = (None if value is None else
                    {'page': page_number, 'start': start, 'end': start + len(value), 'quote': value})
            entry['expected_unverified_fields'] = [field for field, value in spec['fields'].items() if value is None]
        elif spec['key'] in ('report-15-pages', 'insufficient-actions', 'missing-evidence', 'textless-page'):
            entry['expected_bullet_output'] = {
                'bullets': ([{'text': spec.get('unsupported') or entry['pages'][0]['text'],
                              'unverified': bool(spec.get('unsupported')),
                              'source_pages': [] if spec.get('unsupported') else [1]}]
                            if spec['pages'][0] else []),
                'actions': [{'text': entry['pages'][page - 1]['text'], 'source_pages': [page],
                             'unverified': False} for page in spec.get('actions', [])],
                'limitation_required': len(spec.get('actions', [])) < 2}
        answers['documents'].append(entry)
    by_key = {doc['key']: doc for doc in answers['documents']}
    for query in answers['search']:
        for hit in query['hits']:
            text = by_key[hit['key']]['pages'][hit['page'] - 1]['text']
            hit.update(snippet=text, start=0, end=len(text))
    (destination / 'expected.json').write_text(json.dumps(answers, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return answers


def controlled_output(spec, excerpts, mode):
    """Provider-wire fixture: source IDs are resolved from real extracted text."""
    def claim(text, quote=None):
        ids = [source_id for source_id, source in excerpts if (quote or text) in source] if text else []
        return {'t': text, 's': ids or None}
    result = {'label': spec.get('ai_label', 'Contract'), 'confidence': spec.get('confidence', 90)}
    if mode == 'table':
        result.update({field: claim(value) for field, value in spec['fields'].items()})
    else:
        result['bullets'] = [claim(spec.get('unsupported') or spec['pages'][0]['text'])]
        result['actions'] = [claim(spec['pages'][page - 1]['text']) for page in spec.get('actions', [])]
        if spec.get('limitation'):
            result['limitation'] = spec['limitation']
    return result


def seed_account(session_factory, storage, owner_id, fixture_dir=FIXTURES, count=20):
    """Extend a fixture account from 10 to 20 without overwriting edits/renewals.

    Only inserts missing fixture filenames; never deletes existing user content.
    Caller supplies a test/demo owner; this function does not create credentials.
    """
    from app.models import Document, Folder, FileFormat, ReviewState
    from app.services.reader_extraction import extract_document_for_reader
    if type(count) is not int or not 1 <= count <= 20:
        raise ValueError('Acceptance document count must be between 1 and 20.')
    answers = json.loads((Path(fixture_dir) / 'expected.json').read_text(encoding='utf-8'))
    document_ids = []
    with session_factory() as db:
        folders = {folder.name: folder for folder in db.query(Folder).filter_by(owner_id=owner_id)}
        for name in ('Economics 101', 'Research'):
            if name not in folders:
                folders[name] = Folder(owner_id=owner_id, name=name)
                db.add(folders[name])
        db.flush()
        for spec in answers['documents'][:count]:
            document = db.query(Document).filter_by(owner_id=owner_id, original_filename=spec['filename']).first()
            if document is None:
                path = Path(storage).resolve() / str(owner_id) / spec['filename']
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(Path(fixture_dir) / spec['filename'], path)
                now = datetime.utcnow()
                document = Document(owner_id=owner_id, original_filename=spec['filename'], storage_path=str(path),
                    file_format=FileFormat.PDF, file_size_bytes=path.stat().st_size,
                    folder_id=folders[spec['folder']].id if spec['folder'] else None,
                    ai_label=spec.get('ai_label', 'Contract'), ai_confidence=spec.get('confidence', 90) / 100,
                    user_label=spec.get('user_label'), review_state=ReviewState.NEEDS_REVIEW,
                    last_accessed_at=now, expires_at=now + timedelta(days=30))
                db.add(document)
                db.flush()
            document_ids.append(document.id)
        db.commit()
    for document_id in document_ids:
        extract_document_for_reader(document_id, session_factory)
    return document_ids


def seed_local():
    from app.core.config import settings
    from app.core.security import get_password_hash
    from app.db.database import SessionLocal
    from app.models import User
    with SessionLocal() as db:
        user = db.query(User).filter_by(username='acceptance145').first()
        if user is None:
            user = User(username='acceptance145', email='acceptance145@example.invalid',
                        password_hash=get_password_hash('Acceptance145!Local'))
            db.add(user)
            db.commit()
        owner_id = user.id
    seed_account(SessionLocal, settings.STORAGE_DIR, owner_id)
    print('Seeded acceptance145: 20 fixture documents (existing user edits preserved).')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=FIXTURES)
    args = parser.parse_args()
    build(args.output)
    print('Prepared 20 synthetic PDFs and expected.json.')
