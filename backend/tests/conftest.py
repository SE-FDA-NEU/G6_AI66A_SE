"""Isolated API tests: never load local credentials or connect to MySQL."""
import os
import sys
from pathlib import Path

os.environ["DB_PASSWORD"] = "unused-test-value"
os.environ["SECRET_KEY"] = "isolated-upload-validation-test-key"
os.environ['GEMINI_API_KEY'] = ''  # tests never spend a developer's real quota
os.environ['RETENTION_CLEANUP_ENABLED'] = 'false'  # explicit cleanup tests use isolated storage
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base, get_db
from app.models import User
from app.services.job_queue import get_job_queue
from app.core.config import settings
from app.core.security import create_access_token


@pytest.fixture
def session_factory():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add(User(id=123, username='upload_user', email='upload@example.com', password_hash='unused'))
        db.add(User(id=124, username='other_user', email='other@example.com', password_hash='unused'))
        db.commit()
    yield factory
    engine.dispose()


@pytest.fixture
def job_queue(session_factory):
    class RecordingQueue:
        def __init__(self):
            self.session_factory = session_factory
            self.enqueued = []

        def enqueue(self, job_id):
            self.enqueued.append(job_id)
    return RecordingQueue()


@pytest.fixture
def client(session_factory, job_queue, tmp_path, monkeypatch):
    def test_db():
        with session_factory() as db:
            yield db
    monkeypatch.setattr(settings, 'STORAGE_DIR', tmp_path / 'uploads')
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[get_job_queue] = lambda: job_queue
    try:
        with TestClient(app) as client:
            client.headers['Authorization'] = f"Bearer {create_access_token({'sub': '123'})}"
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)
