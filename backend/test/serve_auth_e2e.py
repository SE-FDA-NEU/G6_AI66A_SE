"""Real auth/document APIs with an in-memory DB; never connects to local MySQL."""
import os
import sys
import atexit
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DB_PASSWORD'] = 'unused-test-password'
os.environ['SECRET_KEY'] = 'isolated-playwright-test-key-not-for-production'
os.environ['GEMINI_API_KEY'] = ''
os.environ['RETENTION_CLEANUP_ENABLED'] = 'false'

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.database import Base, get_db
from app.models import User, Document, FileFormat, Folder, Job, JobFile, JobMode, JobStatus, ReviewState
from app.core.security import get_password_hash
from app.core.config import settings
from app.services.reader_extraction import extract_document_for_reader
import app.main as main_module

engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
Base.metadata.create_all(engine)
TestSession = sessionmaker(bind=engine)
main_module.SessionLocal = TestSession
test_storage = tempfile.TemporaryDirectory(prefix='documind-reader-e2e-')
settings.STORAGE_DIR = Path(test_storage.name)
atexit.register(test_storage.cleanup)


def metadata_pdf(path):
    objects = ['<< /Type /Catalog /Pages 2 0 R >>',
               '<< /Type /Pages /Count 2 /Kids [4 0 R 6 0 R] >>',
               '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    for page in (1, 2):
        stream = f'BT /F1 12 Tf 72 720 Td (Metadata source page {page}) Tj ET'
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {len(objects) + 2} 0 R >>')
        objects.append(f'<< /Length {len(stream)} >>\nstream\n{stream}\nendstream')
    pdf = '%PDF-1.4\n'
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf)); pdf += f'{number} 0 obj\n{obj}\nendobj\n'
    xref = len(pdf)
    pdf += f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'
    pdf += ''.join(f'{offset:010d} 00000 n \n' for offset in offsets[1:])
    pdf += f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'
    path.write_bytes(pdf.encode('ascii'))


review_document_ids = []
with TestSession() as db:
    db.add(User(username='playwright_user', email='playwright@example.com',
                password_hash=get_password_hash('LocalIssueTest2026!')))
    db.add(User(username='playwright_other', email='other@example.com',
                password_hash=get_password_hash('LocalIssueTest2026!')))
    db.add(User(username='reader_user', email='reader@example.com',
                password_hash=get_password_hash('LocalIssueTest2026!')))
    db.add(User(username='workspace_user', email='workspace@example.com',
                password_hash=get_password_hash('LocalIssueTest2026!')))
    db.add(User(username='folder_user', email='folder@example.com',
                password_hash=get_password_hash('LocalIssueTest2026!')))
    db.add(User(username='label_user', email='label@example.com',
                password_hash=get_password_hash('LocalIssueTest2026!')))
    db.add(User(username='review_user', email='review@example.com',
                password_hash=get_password_hash('LocalIssueTest2026!')))
    db.flush()
    for owner in db.query(User).all():
        if owner.username in ('label_user', 'review_user'):
            continue
        db.add(Document(
            owner_id=owner.id,
            original_filename=f'private-{owner.username}.pdf',
            storage_path=f'/private/{owner.username}/confidential.pdf',
            file_format=FileFormat.PDF,
            file_size_bytes=128,
            ai_label='Economics' if owner.username == 'folder_user' else None,
            ai_confidence=.91 if owner.username == 'folder_user' else None,
            user_label='Semester 1' if owner.username == 'folder_user' else None,
            review_state=ReviewState.CONFIRMED if owner.username == 'folder_user' else ReviewState.NEEDS_REVIEW,
            extracted_text=[{'page': 1, 'text': f'Confidential content for {owner.username}'}],
            last_accessed_at=datetime(2026, 1, 1),
            expires_at=datetime(2026, 1, 1) + timedelta(days=30),
        ))
    db.flush()
    label_owner = db.query(User).filter_by(username='label_user').one()
    label_folders = [Folder(owner_id=label_owner.id, name=name) for name in ['Economics 101', 'Research']]
    db.add_all(label_folders)
    db.flush()
    for number in range(20):
        db.add(Document(owner_id=label_owner.id, folder_id=label_folders[number % 2].id,
                        original_filename=f'label-document-{number}.pdf', storage_path=f'/fixture/label-{number}.pdf',
                        file_format=FileFormat.PDF, file_size_bytes=128,
                        ai_label='Macroeconomics' if number < 8 else 'Microeconomics', ai_confidence=.91,
                        user_label='User correction' if number < 8 else 'Macroeconomics',
                        created_at=datetime(2026, 1, 1) + timedelta(seconds=number),
                        expires_at=datetime.utcnow() + timedelta(days=30)))
    reviewer = db.query(User).filter_by(username='review_user').one()
    review_folder = Folder(owner_id=reviewer.id, name='Economics 101')
    db.add(review_folder); db.flush()
    for score in (.79, .8):
        source = Path(test_storage.name) / f'review-{score}.pdf'
        metadata_pdf(source)
        review_document = Document(owner_id=reviewer.id, folder_id=review_folder.id,
                                   original_filename=source.name, storage_path=str(source), file_format=FileFormat.PDF,
                                   file_size_bytes=source.stat().st_size, ai_label='Macroeconomics', ai_confidence=score,
                                   review_state=ReviewState.NEEDS_REVIEW, expires_at=datetime.utcnow() + timedelta(days=30))
        db.add(review_document); db.flush(); review_document_ids.append(review_document.id)
    owner = db.query(User).filter_by(username='playwright_user').one()
    document = db.query(Document).filter_by(owner_id=owner.id).one()
    completed_job = Job(id=9001, owner_id=owner.id, mode=JobMode.BULLET,
                        status=JobStatus.COMPLETED, file_count=1, completed_count=1,
                        finished_at=datetime(2026, 1, 1))
    db.add(completed_job)
    db.add(JobFile(job=completed_job, document=document, status=JobStatus.COMPLETED,
                   attempt_count=1, timeout_seconds=33))
    # Dedicated saved comparison for browser download tests; no model or local DB.
    export_owner = User(username='export_user', email='export@example.com',
                        password_hash=get_password_hash('LocalIssueTest2026!'))
    db.add(export_owner); db.flush()
    export_job = Job(id=9002, owner_id=export_owner.id, mode=JobMode.TABLE,
                     status=JobStatus.COMPLETED, file_count=5, completed_count=5,
                     finished_at=datetime(2026, 1, 1))
    export_rows = {}
    db.add(export_job)
    for index, amount in enumerate(['1,200,000,000 VND', '2,500,000,000 VND', '999,999.99 USD',
                                    '0.00 VND', '750,000,000 VND']):
        doc = Document(owner_id=export_owner.id, original_filename=f'Hợp đồng {index + 1}.pdf',
                       storage_path=f'/fixture/export-{index + 1}.pdf', file_format=FileFormat.PDF,
                       file_size_bytes=128, expires_at=datetime.utcnow() + timedelta(days=30))
        db.add(doc); db.flush()
        db.add(JobFile(job=export_job, document=doc, status=JobStatus.COMPLETED,
                       attempt_count=1, timeout_seconds=60))

        def export_claim(text, page):
            return {'text': text, 'unverified': False, 'evidence': [{
                'document_id': doc.id, 'page': page, 'start': 0, 'end': len(text),
                'quote': text, 'reader_version': 'a' * 64,
            }]}

        output = {'type': 'table', 'value': export_claim(amount, 1),
                  'payment_term': export_claim('Thanh toán trong 30 ngày', 2),
                  'penalty': export_claim('0.05% per day', 3)}
        if index == 4:
            output['payment_term'] = {'text': None, 'unverified': True, 'evidence': []}
        if index == 3:
            output['penalty']['unverified'] = True
            output['penalty']['verification_issues'] = ['unsupported_fact']
        export_rows[str(doc.id)] = {
            'schema_version': 1, 'document_id': doc.id, 'original_filename': doc.original_filename,
            'mode': 'table', 'analysis_status': 'completed', 'warnings': [],
            'reader': {'version': 'a' * 64, 'page_count': 3, 'page_kind': 'page',
                       'url': f'/documents/{doc.id}/reader.pdf'},
            'label': {'ai_label': 'Hợp đồng', 'ai_confidence': .9, 'review_state': 'needs_review',
                      'confidence_level': 'high', 'user_label': None}, 'output': output,
        }
    export_job.result_data = {'schema_version': 1, 'documents': export_rows}
    incomplete_export_job = Job(id=9003, owner_id=export_owner.id, mode=JobMode.TABLE,
                                status=JobStatus.COMPLETED, file_count=5, completed_count=4,
                                result_data={'schema_version': 1, 'documents': {}})
    db.add(incomplete_export_job)
    db.commit()

for document_id in review_document_ids:
    extract_document_for_reader(document_id, TestSession)


def test_db():
    with TestSession() as db:
        yield db


app.dependency_overrides[get_db] = test_db

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=18001)
