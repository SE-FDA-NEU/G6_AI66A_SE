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


def ensure_fixtures_built(fixture_dir=FIXTURES):
    fixture_dir = Path(fixture_dir)
    expected_path = fixture_dir / 'expected.json'
    if not expected_path.is_file():
        return build(fixture_dir)
    answers = json.loads(expected_path.read_text(encoding='utf-8'))
    for spec in answers.get('documents', []):
        pdf_path = fixture_dir / spec['filename']
        if not pdf_path.is_file() or hashlib.sha256(pdf_path.read_bytes()).hexdigest() != spec['sha256']:
            return build(fixture_dir)
    return answers


def seed_account(session_factory, storage, owner_id, fixture_dir=FIXTURES, count=20):
    """Extend a fixture account from 10 to 20 without overwriting edits/renewals.

    Only inserts missing fixture filenames; never deletes existing user content.
    Caller supplies a test/demo owner; this function does not create credentials.
    """
    from app.models import Document, Folder, FileFormat, ReviewState
    from app.services.document_retention import is_expired_source
    from app.services.reader_extraction import extract_document_for_reader
    if type(count) is not int or not 1 <= count <= 20:
        raise ValueError('Acceptance document count must be between 1 and 20.')
    answers = ensure_fixtures_built(fixture_dir)
    document_ids = []
    now = datetime.utcnow()
    with session_factory() as db:
        folders = {folder.name: folder for folder in db.query(Folder).filter_by(owner_id=owner_id)}
        for name in ('Economics 101', 'Research'):
            if name not in folders:
                folders[name] = Folder(owner_id=owner_id, name=name)
                db.add(folders[name])
        db.flush()
        for spec in answers['documents'][:count]:
            document = db.query(Document).filter_by(owner_id=owner_id, original_filename=spec['filename']).first()
            path = Path(storage).resolve() / str(owner_id) / spec['filename']
            if document is None:
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(Path(fixture_dir) / spec['filename'], path)
                document = Document(owner_id=owner_id, original_filename=spec['filename'], storage_path=str(path),
                    file_format=FileFormat.PDF, file_size_bytes=path.stat().st_size,
                    folder_id=folders[spec['folder']].id if spec['folder'] else None,
                    ai_label=spec.get('ai_label', 'Contract'), ai_confidence=spec.get('confidence', 90) / 100,
                    user_label=spec.get('user_label'), review_state=ReviewState.NEEDS_REVIEW,
                    last_accessed_at=now, expires_at=now + timedelta(days=30))
                db.add(document)
                db.flush()
            elif not is_expired_source(document):
                # Restore missing disk file if needed and keep retention healthy without touching user edits.
                target_path = Path(document.storage_path)
                if not target_path.is_file():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(Path(fixture_dir) / spec['filename'], path)
                    document.storage_path = str(path)
                if document.expires_at < now + timedelta(days=14):
                    document.last_accessed_at = now
                    document.expires_at = now + timedelta(days=30)
            document_ids.append(document.id)
        db.commit()
    for document_id in document_ids:
        extract_document_for_reader(document_id, session_factory)
    return document_ids


DEMO_ACCOUNTS = (
    {
        'key': 'primary',
        'username': 'acceptance145',
        'email': 'acceptance145@example.invalid',
        'password_env': 'DOCUMIND_DEMO_PASSWORD_A',
        'default_password': 'Acceptance145!Local',
    },
    {
        'key': 'peer',
        'username': 'peer145',
        'email': 'peer145@example.invalid',
        'password_env': 'DOCUMIND_DEMO_PASSWORD_B',
        'default_password': 'Peer145!Local',
    },
)


def write_docx_sample(path: Path, title: str, paragraphs: list[str], table_rows: list[tuple[str, str]]) -> Path:
    from docx import Document as WordDocument
    doc = WordDocument()
    doc.add_paragraph(title)
    for idx, paragraph in enumerate(paragraphs):
        if idx == 1:
            doc.add_page_break()
        doc.add_paragraph(paragraph)
    if table_rows:
        table = doc.add_table(rows=len(table_rows), cols=2)
        for row_idx, (left, right) in enumerate(table_rows):
            table.cell(row_idx, 0).text = left
            table.cell(row_idx, 1).text = right
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return path


def write_pptx_sample(path: Path, slides_text: list[str]) -> Path:
    from pptx import Presentation
    from pptx.util import Inches
    deck = Presentation()
    for index, text in enumerate(slides_text):
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        if text:
            slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(2)).text = text
        if index == 1:
            slide._element.set('show', '0')
        slide.notes_slide.notes_text_frame.text = 'Synthetic speaker note excluded from reader pages.'
    path.parent.mkdir(parents=True, exist_ok=True)
    deck.save(path)
    return path


def seed_office_samples(session_factory, storage, owner_id, *, prefix='sample'):
    """Seed non-sensitive DOCX and PPTX files and prepare their .reader PDFs."""
    from app.models import Document, FileFormat, Folder, ReviewState
    from app.services.document_retention import is_expired_source
    from app.services.reader_extraction import extract_document_for_reader

    now = datetime.utcnow()
    owner_dir = Path(storage).resolve() / str(owner_id)
    owner_dir.mkdir(parents=True, exist_ok=True)

    specs = [
        {
            'filename': f'{prefix}-policy-handbook.docx',
            'format': FileFormat.DOCX,
            'ai_label': 'Policy',
            'confidence': 0.91,
            'user_label': 'Operations policy',
            'folder': 'Research',
            'writer': lambda target: write_docx_sample(
                target,
                'Synthetic Procurement and Retention Policy Handbook',
                [
                    'Section 1. Supplier quotations must be compared before contract renewal. Payment term is Within 30 days.',
                    'Section 2. Document retention renews for 30 days on authorized access. Late payment penalty is 0.05% per day.',
                ],
                [('Policy clause', 'Requirement'), ('Retention window', '30 days after access')],
            ),
        },
        {
            'filename': f'{prefix}-architecture-deck.pptx',
            'format': FileFormat.PPTX,
            'ai_label': 'Architecture',
            'confidence': 0.87,
            'user_label': None,
            'folder': 'Economics 101',
            'writer': lambda target: write_pptx_sample(
                target,
                [
                    'Slide 1: DocuMind Native Reader Architecture Overview and Evidence Verification.',
                    'Slide 2: Multi-Document Comparison Table and Citation Highlighting Pipeline.',
                    'Slide 3: Cross-Document Keyword and Semantic Retrieval Summary.',
                ],
            ),
        },
    ]

    doc_ids = []
    with session_factory() as db:
        folders = {folder.name: folder for folder in db.query(Folder).filter_by(owner_id=owner_id)}
        for name in ('Economics 101', 'Research'):
            if name not in folders:
                folders[name] = Folder(owner_id=owner_id, name=name)
                db.add(folders[name])
        db.flush()

        for spec in specs:
            doc = db.query(Document).filter_by(owner_id=owner_id, original_filename=spec['filename']).first()
            file_path = owner_dir / spec['filename']
            if doc is None:
                spec['writer'](file_path)
                doc = Document(
                    owner_id=owner_id,
                    original_filename=spec['filename'],
                    storage_path=str(file_path),
                    file_format=spec['format'],
                    file_size_bytes=file_path.stat().st_size,
                    folder_id=folders[spec['folder']].id if spec['folder'] else None,
                    ai_label=spec['ai_label'],
                    ai_confidence=spec['confidence'],
                    user_label=spec['user_label'],
                    review_state=ReviewState.NEEDS_REVIEW,
                    last_accessed_at=now,
                    expires_at=now + timedelta(days=30),
                )
                db.add(doc)
                db.flush()
            elif not is_expired_source(doc):
                target_path = Path(doc.storage_path)
                if not target_path.is_file():
                    spec['writer'](file_path)
                    doc.storage_path = str(file_path)
                if doc.expires_at < now + timedelta(days=14):
                    doc.last_accessed_at = now
                    doc.expires_at = now + timedelta(days=30)
            doc_ids.append(doc.id)
        db.commit()

    for doc_id in doc_ids:
        extract_document_for_reader(doc_id, session_factory)
    return doc_ids


def _build_validated_demo_analyzer(answers_by_filename):
    from app.schemas.result import (
        AnalysisMetadata,
        AnalysisResult,
        BulletOutput,
        Claim,
        Concept,
        ConceptOutput,
        Evidence,
        LabelSuggestion,
        TableOutput,
    )

    def make_claim(document, page_number, quote, text=None, kind='general'):
        page_entry = document.extracted_text[page_number - 1]
        page_text = page_entry['text']
        start = page_text.index(quote)
        end = start + len(quote)
        return Claim(
            text=text if text is not None else quote,
            kind=kind,
            unverified=False,
            evidence=[
                Evidence(
                    document_id=document.id,
                    page=page_number,
                    start=start,
                    end=end,
                    quote=quote,
                    reader_version=page_entry['reader']['sha256'],
                )
            ],
        )

    async def analyzer(document, mode):
        with_meta = AnalysisMetadata(
            provider='gemini',
            model='gemini-3.5-flash',
            prompt_version='seed-p0-v1',
            cache_hit=True,
            input_truncated=False,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
        )
        page1 = document.extracted_text[0]['text']
        first_line = next((line.strip() for line in page1.splitlines() if line.strip()), page1.strip())
        spec = None
        for filename, candidate in answers_by_filename.items():
            if filename.startswith('contract-') and filename[:-4].replace('-', ' ').lower() in page1.lower():
                spec = candidate
                break
        if mode.value == 'table':
            if spec and 'fields' in spec:
                val = spec['fields']['value']
                term = spec['fields']['payment_term']
                pen = spec['fields']['penalty']
                output = TableOutput(
                    value=make_claim(document, 1, val, val, 'amount'),
                    payment_term=make_claim(document, 2, term, term, 'clause') if term else Claim(text=None, unverified=True),
                    penalty=make_claim(document, 3, pen, pen, 'clause'),
                )
                label = LabelSuggestion(ai_label='Contract', ai_confidence=spec.get('confidence', 90) / 100)
                return AnalysisResult(output=output, label=label, analysis_metadata=with_meta)
            output = TableOutput(
                value=make_claim(document, 1, first_line, first_line, 'amount'),
                payment_term=Claim(text=None, unverified=True),
                penalty=Claim(text=None, unverified=True),
            )
            return AnalysisResult(output=output, label=LabelSuggestion(ai_label='Contract', ai_confidence=0.9), analysis_metadata=with_meta)

        if mode.value == 'bullet':
            bullets = [make_claim(document, 1, first_line)]
            actions = []
            if len(document.extracted_text) >= 3:
                p2_line = document.extracted_text[1]['text'].strip()
                p3_line = document.extracted_text[2]['text'].strip()
                if p2_line:
                    actions.append(make_claim(document, 2, p2_line))
                if p3_line:
                    actions.append(make_claim(document, 3, p3_line))
            limitation = None if len(actions) >= 2 else 'The source provides fewer than two explicit action items.'
            return AnalysisResult(
                output=BulletOutput(bullets=bullets, actions=actions, limitation=limitation),
                label=LabelSuggestion(ai_label='Report', ai_confidence=0.9),
                analysis_metadata=with_meta,
            )

        concepts = []
        for idx, page in enumerate(document.extracted_text[:3], start=1):
            line = next((ln.strip() for ln in page['text'].splitlines() if ln.strip()), '')
            if line:
                concepts.append(Concept(name=f'Core Concept {idx}', description=make_claim(document, idx, line)))
        limitation = None if len(concepts) >= 3 else 'The source supports fewer than three core concepts.'
        return AnalysisResult(
            output=ConceptOutput(concepts=concepts, limitation=limitation),
            label=LabelSuggestion(ai_label='Concept Study', ai_confidence=0.88),
            analysis_metadata=with_meta,
        )

    return analyzer


def seed_p0_jobs(session_factory, owner_id, fixture_dir=FIXTURES, *, use_live_ai=False):
    """Ensure completed Table, Bullet and Concept jobs with verified citations exist for owner_id."""
    from app.core.config import settings
    from app.models import Document, Job, JobFile, JobMode, JobStatus
    from app.services import processing

    answers = ensure_fixtures_built(fixture_dir)
    answers_by_filename = {doc['filename']: doc for doc in answers['documents']}
    analyzer = None
    if not (use_live_ai and settings.GEMINI_API_KEY.get_secret_value().strip()):
        analyzer = _build_validated_demo_analyzer(answers_by_filename)

    with session_factory() as db:
        docs_by_name = {
            doc.original_filename: doc
            for doc in db.query(Document).filter_by(owner_id=owner_id).all()
        }
        existing_modes = {
            job.mode
            for job in db.query(Job).filter_by(owner_id=owner_id, status=JobStatus.COMPLETED).all()
            if job.result_data and job.result_data.get('documents')
        }

        plans = []
        contract_docs = [docs_by_name[f'contract-{i}.pdf'] for i in range(1, 6) if f'contract-{i}.pdf' in docs_by_name]
        if len(contract_docs) == 5 and JobMode.TABLE not in existing_modes:
            plans.append((JobMode.TABLE, contract_docs))

        if 'report-15-pages.pdf' in docs_by_name and JobMode.BULLET not in existing_modes:
            plans.append((JobMode.BULLET, [docs_by_name['report-15-pages.pdf']]))

        concept_targets = [
            docs_by_name[name]
            for name in ('sample-architecture-deck.pptx', 'sample-policy-handbook.docx', 'course-note-01.pdf')
            if name in docs_by_name
        ]
        if concept_targets and JobMode.CONCEPT not in existing_modes:
            plans.append((JobMode.CONCEPT, [concept_targets[0]]))

        created_job_ids = []
        for mode, target_docs in plans:
            job = Job(
                owner_id=owner_id,
                mode=mode,
                status=JobStatus.PENDING,
                file_count=len(target_docs),
                completed_count=0,
                result_data={'schema_version': 1, 'language': 'vi', 'documents': {}},
            )
            db.add(job)
            db.flush()
            for doc in target_docs:
                db.add(JobFile(job_id=job.id, document_id=doc.id, status=JobStatus.PENDING))
            db.commit()
            created_job_ids.append(job.id)

    for job_id in created_job_ids:
        processing.process_job(job_id, session_factory, analyzer=analyzer)

    with session_factory() as db:
        return [
            job.id
            for job in db.query(Job).filter_by(owner_id=owner_id, status=JobStatus.COMPLETED).order_by(Job.id).all()
        ]


def seed_peer_account(session_factory, storage, owner_id, fixture_dir=FIXTURES):
    """Seed isolated documents and a completed Table job for the secondary account (US05 ownership)."""
    from app.models import Document, FileFormat, Folder, Job, JobFile, JobMode, JobStatus, ReviewState
    from app.services import processing
    from app.services.document_retention import is_expired_source
    from app.services.reader_extraction import extract_document_for_reader

    answers = ensure_fixtures_built(fixture_dir)
    answers_by_filename = {doc['filename']: doc for doc in answers['documents']}
    now = datetime.utcnow()
    owner_dir = Path(storage).resolve() / str(owner_id)
    owner_dir.mkdir(parents=True, exist_ok=True)

    doc_ids = []
    with session_factory() as db:
        folder = db.query(Folder).filter_by(owner_id=owner_id, name='Peer Contracts').first()
        if folder is None:
            folder = Folder(owner_id=owner_id, name='Peer Contracts')
            db.add(folder)
            db.flush()

        pdf_doc = db.query(Document).filter_by(owner_id=owner_id, original_filename='contract-1.pdf').first()
        pdf_path = owner_dir / 'contract-1.pdf'
        if pdf_doc is None:
            shutil.copyfile(Path(fixture_dir) / 'contract-1.pdf', pdf_path)
            pdf_doc = Document(
                owner_id=owner_id,
                original_filename='contract-1.pdf',
                storage_path=str(pdf_path),
                file_format=FileFormat.PDF,
                file_size_bytes=pdf_path.stat().st_size,
                folder_id=folder.id,
                ai_label='Contract',
                ai_confidence=0.90,
                user_label='Peer B Contract',
                review_state=ReviewState.CONFIRMED,
                last_accessed_at=now,
                expires_at=now + timedelta(days=30),
            )
            db.add(pdf_doc)
            db.flush()
        elif not is_expired_source(pdf_doc):
            if not Path(pdf_doc.storage_path).is_file():
                shutil.copyfile(Path(fixture_dir) / 'contract-1.pdf', pdf_path)
                pdf_doc.storage_path = str(pdf_path)
            if pdf_doc.expires_at < now + timedelta(days=14):
                pdf_doc.last_accessed_at = now
                pdf_doc.expires_at = now + timedelta(days=30)
        doc_ids.append(pdf_doc.id)
        db.commit()

    extract_document_for_reader(doc_ids[0], session_factory)
    office_ids = seed_office_samples(session_factory, storage, owner_id, prefix='peer')
    doc_ids.extend(office_ids)

    with session_factory() as db:
        has_job = db.query(Job).filter_by(owner_id=owner_id, status=JobStatus.COMPLETED).first()
        job_id = None
        if has_job is None:
            job = Job(
                owner_id=owner_id,
                mode=JobMode.TABLE,
                status=JobStatus.PENDING,
                file_count=1,
                completed_count=0,
                result_data={'schema_version': 1, 'language': 'vi', 'documents': {}},
            )
            db.add(job)
            db.flush()
            db.add(JobFile(job_id=job.id, document_id=doc_ids[0], status=JobStatus.PENDING))
            db.commit()
            job_id = job.id

    if job_id is not None:
        processing.process_job(
            job_id,
            session_factory,
            analyzer=_build_validated_demo_analyzer(answers_by_filename),
        )
    return doc_ids


def seed_production_demo(session_factory=None, storage=None, fixture_dir=FIXTURES, *, use_live_ai=False):
    """Idempotently prepare Account A + Account B, 20 PDFs + DOCX/PPTX, and Table/Bullet/Concept jobs."""
    import os
    from app.core.config import settings
    from app.core.security import get_password_hash
    from app.db.database import SessionLocal
    from app.models import User

    factory = session_factory or SessionLocal
    storage_root = Path(storage if storage is not None else settings.STORAGE_DIR).resolve()
    account_ids = {}

    with factory() as db:
        for spec in DEMO_ACCOUNTS:
            user = db.query(User).filter(
                (User.username == spec['username']) | (User.email == spec['email'])
            ).first()
            if user is None:
                password = os.environ.get(spec['password_env']) or spec['default_password']
                user = User(
                    username=spec['username'],
                    email=spec['email'],
                    password_hash=get_password_hash(password),
                )
                db.add(user)
                db.flush()
            account_ids[spec['key']] = user.id
        db.commit()

    primary_id = account_ids['primary']
    peer_id = account_ids['peer']

    pdf_ids = seed_account(factory, storage_root, primary_id, fixture_dir=fixture_dir, count=20)
    office_ids = seed_office_samples(factory, storage_root, primary_id, prefix='sample')
    job_ids = seed_p0_jobs(factory, primary_id, fixture_dir=fixture_dir, use_live_ai=use_live_ai)
    peer_doc_ids = seed_peer_account(factory, storage_root, peer_id, fixture_dir=fixture_dir)

    return {
        'primary_owner_id': primary_id,
        'peer_owner_id': peer_id,
        'primary_pdf_ids': pdf_ids,
        'primary_office_ids': office_ids,
        'primary_job_ids': job_ids,
        'peer_document_ids': peer_doc_ids,
    }


def seed_local(use_live_ai=False):
    summary = seed_production_demo(use_live_ai=use_live_ai)
    print(
        f"Seeded production demo accounts: acceptance145 ({len(summary['primary_pdf_ids'])} PDFs + "
        f"{len(summary['primary_office_ids'])} Office files, {len(summary['primary_job_ids'])} completed jobs) "
        f"and peer145 ({len(summary['peer_document_ids'])} isolated documents)."
    )
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=FIXTURES)
    args = parser.parse_args()
    build(args.output)
    print('Prepared 20 synthetic PDFs and expected.json.')
