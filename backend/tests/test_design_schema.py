"""The design's six tables are authoritative, including migration of old installs."""
import json
from pathlib import Path
import re
import sys

import pytest
from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table, inspect

from app.db.database import Base

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from restore_design_schema import DESIGN_TABLES, restore_design_schema


def test_models_match_table_and_column_definitions_in_design():
    design = (Path(__file__).resolve().parents[2] / 'docs' / 'design.md').read_text(encoding='utf-8')
    definitions = {}
    for line in design.splitlines():
        match = re.match(r'\| \*\*([a-z_]+)\*\*', line)
        if match and match[1] in DESIGN_TABLES:
            definitions[match[1]] = set(re.findall(r'`([a-z_]+)`', line.split('|')[2]))
    assert set(Base.metadata.tables) == set(definitions) == DESIGN_TABLES
    for name, columns in definitions.items():
        assert set(Base.metadata.tables[name].columns.keys()) == columns


@pytest.fixture
def old_database(session_factory):
    engine = session_factory.kw['bind']
    metadata = MetaData()
    metadata.reflect(engine)
    legacy = []
    for name, parent in [('search_documents', 'documents'), ('search_passages', 'search_documents'), ('search_terms', 'search_passages')]:
        legacy.append(Table(name, metadata, Column('id', Integer, primary_key=True),
                            Column('parent_id', Integer, ForeignKey(f'{parent}.id'))))
    metadata.create_all(engine)
    with engine.begin() as connection:
        # The legacy index is derived; tests also cover a nonempty backup.
        for table in legacy:
            connection.execute(table.insert().values(id=1, parent_id=None))
    return engine


def test_restore_backs_up_before_dropping_only_retired_tables_and_is_idempotent(old_database, tmp_path):
    backup = tmp_path / 'backup.json'
    assert restore_design_schema(old_database, backup) == 3
    assert set(inspect(old_database).get_table_names()) == DESIGN_TABLES
    saved = json.loads(backup.read_text(encoding='utf-8'))['tables']
    assert set(saved) == DESIGN_TABLES | {'search_documents', 'search_passages', 'search_terms'}
    assert all(saved[name] == [{'id': 1, 'parent_id': None}] for name in ('search_documents', 'search_passages', 'search_terms'))
    assert len(saved['users']) == 2
    assert restore_design_schema(old_database, backup) == 0


def test_existing_backup_cannot_be_overwritten_or_tables_dropped(old_database, tmp_path):
    backup = tmp_path / 'backup.json'
    backup.write_text('existing backup', encoding='utf-8')
    with pytest.raises(FileExistsError):
        restore_design_schema(old_database, backup)
    assert len(inspect(old_database).get_table_names()) == 9
    assert backup.read_text(encoding='utf-8') == 'existing backup'


def test_unexpected_schema_is_not_modified(old_database, tmp_path):
    metadata = MetaData()
    Table('unrelated', metadata, Column('id', Integer, primary_key=True))
    metadata.create_all(old_database)
    with pytest.raises(RuntimeError, match='Unexpected schema'):
        restore_design_schema(old_database, tmp_path / 'backup.json')
    assert len(inspect(old_database).get_table_names()) == 10
    assert not (tmp_path / 'backup.json').exists()
