"""Real auth API with an in-memory test DB; never connects to local MySQL."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DB_PASSWORD'] = 'unused-test-password'
os.environ['SECRET_KEY'] = 'isolated-playwright-test-key-not-for-production'

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.database import Base, get_db
from app.models import User
from app.core.security import get_password_hash

engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
Base.metadata.create_all(engine)
TestSession = sessionmaker(bind=engine)
with TestSession() as db:
    db.add(User(username='playwright_user', email='playwright@example.com',
                password_hash=get_password_hash('LocalIssueTest2026!')))
    db.commit()


def test_db():
    with TestSession() as db:
        yield db


app.dependency_overrides[get_db] = test_db

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=18001)
