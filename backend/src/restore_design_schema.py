"""Back up and remove only the three retired, derived search-index tables."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from sqlalchemy import MetaData, Table, inspect, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DESIGN_TABLES = {'users', 'folders', 'documents', 'jobs', 'job_files', 'citations'}
RETIRED_TABLES = ('search_terms', 'search_passages', 'search_documents')


def restore_design_schema(bind, backup_path):
    inspector = inspect(bind)
    names = set(inspector.get_table_names())
    if not DESIGN_TABLES.issubset(names) or names - DESIGN_TABLES - set(RETIRED_TABLES):
        raise RuntimeError('Unexpected schema; no tables were removed.')
    retired = [name for name in RETIRED_TABLES if name in names]
    if not retired:
        return 0
    for name in names - set(RETIRED_TABLES):
        if any(key['referred_table'] in RETIRED_TABLES for key in inspector.get_foreign_keys(name)):
            raise RuntimeError('A retained table references a retired table; no tables were removed.')
    metadata = MetaData()
    metadata.reflect(bind)
    with bind.connect() as connection:
        saved = {name: [dict(row) for row in connection.execute(select(metadata.tables[name]).order_by(
            *metadata.tables[name].primary_key.columns)).mappings()]
                 for name in sorted(names)}
    backup_path = Path(backup_path)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    with backup_path.open('x', encoding='utf-8') as handle:
        json.dump({'tables': saved}, handle, ensure_ascii=False, default=str)
        handle.flush()
        os.fsync(handle.fileno())
    # MySQL DDL commits implicitly. Always create the backup before the first DROP.
    for name in retired:
        Table(name, metadata, extend_existing=True).drop(bind, checkfirst=True)
    with bind.connect() as connection:
        for name in DESIGN_TABLES:
            current = [dict(row) for row in connection.execute(select(metadata.tables[name]).order_by(
                *metadata.tables[name].primary_key.columns)).mappings()]
            if current != saved[name]:
                raise RuntimeError('Retained data changed during migration; inspect the backup.')
    if set(inspect(bind).get_table_names()) != DESIGN_TABLES:
        raise RuntimeError('Schema verification failed; inspect the backup.')
    return len(retired)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    from app.db.database import engine
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = Path(__file__).resolve().parents[1] / 'test-results' / f'schema-backup-{stamp}.json'
    removed = restore_design_schema(engine, backup)
    print(f'Design schema verified: 6 tables; removed {removed} retired search tables.')
    if removed:
        print(f'Backup: {backup}')
