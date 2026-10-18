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

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.database import Base, get_db
from app.models import User, Document, FileFormat, Job, JobFile, JobMode, JobStatus
from app.core.security import get_password_hash
from app.core.config import settings
import app.main as main_module

engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
Base.metadata.create_all(engine)
TestSession = sessionmaker(bind=engine)
main_module.SessionLocal = TestSession
test_storage = tempfile.TemporaryDirectory(prefix='documind-reader-e2e-')
settings.STORAGE_DIR = Path(test_storage.name)
atexit.register(test_storage.cleanup)
with TestSession() as db:
    db.add(User(username='playwright_user', email='playwright@example.com',
                password_hash=get_password_hash('LocalIssueTest2026!')))
    db.add(User(username='playwright_other', email='other@example.com',
                password_hash=get_password_hash('LocalIssueTest2026!')))
    db.add(User(username='reader_user', email='reader@example.com',
                password_hash=get_password_hash('LocalIssueTest2026!')))
    db.add(User(username='workspace_user', email='workspace@example.com',
                password_hash=get_password_hash('LocalIssueTest2026!')))
    db.flush()
    for owner in db.query(User).all():
        db.add(Document(
            owner_id=owner.id,
            original_filename=f'private-{owner.username}.pdf',
            storage_path=f'/private/{owner.username}/confidential.pdf',
            file_format=FileFormat.PDF,
            file_size_bytes=128,
            extracted_text=[{'page': 1, 'text': f'Confidential content for {owner.username}'}],
            last_accessed_at=datetime(2026, 1, 1),
            expires_at=datetime(2026, 1, 1) + timedelta(days=30),
        ))
    db.flush()
    owner = db.query(User).filter_by(username='playwright_user').one()
    document = db.query(Document).filter_by(owner_id=owner.id).one()
    completed_job = Job(id=9001, owner_id=owner.id, mode=JobMode.BULLET,
                        status=JobStatus.COMPLETED, file_count=1, completed_count=1,
                        finished_at=datetime(2026, 1, 1))
    db.add(completed_job)
    db.add(JobFile(job=completed_job, document=document, status=JobStatus.COMPLETED,
                   attempt_count=1, timeout_seconds=33))
    db.commit()


def test_db():
    with TestSession() as db:
        yield db


app.dependency_overrides[get_db] = test_db

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=18001)
