"""Add/backfill only the search tables in an existing database; no data is dropped.

Run from backend: .venv/Scripts/python.exe src/init_search_index.py
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import Base, engine, SessionLocal
from app.models import Document, SearchDocument, SearchPassage, SearchTerm
from app.services.search_index import purge_expired_index, reconcile_owner_index
from sqlalchemy.exc import SQLAlchemyError


def initialize_search_index(bind, factory):
    Base.metadata.create_all(bind, tables=[SearchDocument.__table__, SearchPassage.__table__, SearchTerm.__table__])
    with factory() as db:
        purge_expired_index(db)
        owners = [row[0] for row in db.query(Document.owner_id).distinct()]
        for owner in owners:
            reconcile_owner_index(db, owner)
        db.commit()
    return len(owners)


if __name__ == '__main__':
    try:
        owners = initialize_search_index(engine, SessionLocal)
    except SQLAlchemyError:
        print('Cannot initialize search index. Check DB_USER/DB_PASSWORD and database permissions in backend/.env.', file=sys.stderr)
        raise SystemExit(1) from None
    print(f'Search index initialized for {owners} account(s).')
