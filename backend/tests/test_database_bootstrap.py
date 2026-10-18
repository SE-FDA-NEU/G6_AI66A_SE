"""Real MySQL preflight tests; all mutations use uniquely named disposable DBs.

DOCUMIND_MYSQL_TESTS=1 backend/.venv/bin/python -m pytest backend/tests/test_database_bootstrap.py -q
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from pymysql.constants import CLIENT
from sqlalchemy import create_engine, inspect, text

from app.db.bootstrap import mysql_url, prepare_database
from app.db.database import Base
from app.models import User

pytestmark = pytest.mark.skipif(os.environ.get('DOCUMIND_MYSQL_TESTS') != '1', reason='Explicit local MySQL tests only')


@pytest.fixture
def mysql_config():
    values = dotenv_values(Path(__file__).resolve().parents[1] / '.env')
    config = SimpleNamespace(DB_USER=values.get('DB_USER', 'root'), DB_PASSWORD=values.get('DB_PASSWORD', ''),
                             DB_HOST=values.get('DB_HOST', 'localhost'), DB_PORT=values.get('DB_PORT', '3306'),
                             DB_NAME='documind_bootstrap_test_' + uuid4().hex[:12])
    admin = create_engine(mysql_url(config), isolation_level='AUTOCOMMIT')
    try:
        yield config
    finally:
        with admin.connect() as connection:
            name = connection.dialect.identifier_preparer.quote_identifier(config.DB_NAME)
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS {name}')
        admin.dispose()


def test_new_database_creates_all_tables_and_next_start_preserves_data(mysql_config, tmp_path):
    report = prepare_database(mysql_config, Base.metadata, tmp_path)
    assert report.created_database and set(report.created_tables) == set(Base.metadata.tables)
    assert not report.removed_tables and report.backup_path is None
    engine = create_engine(mysql_url(mysql_config, mysql_config.DB_NAME))
    try:
        with engine.begin() as connection:
            connection.execute(User.__table__.insert().values(username='local-test', email='local-test@example.com', password_hash='test-hash'))
        again = prepare_database(mysql_config, Base.metadata, tmp_path)
        assert not again.created_database and not again.created_tables and not again.removed_tables
        assert again.backup_path is None
        with engine.connect() as connection:
            assert connection.execute(text('SELECT username FROM users')).scalar_one() == 'local-test'
    finally:
        engine.dispose()


def test_missing_and_extra_tables_are_synced_after_restorable_backup(mysql_config, tmp_path):
    prepare_database(mysql_config, Base.metadata, tmp_path)
    engine = create_engine(mysql_url(mysql_config, mysql_config.DB_NAME))
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql('DROP TABLE citations')
            connection.exec_driver_sql('CREATE TABLE legacy_parent (id INT PRIMARY KEY, label TEXT, payload JSON, amount DECIMAL(12,2), raw_bytes BLOB, created_at DATETIME, doubled INT GENERATED ALWAYS AS (id * 2) STORED)')
            connection.exec_driver_sql('CREATE TABLE legacy_child (id INT PRIMARY KEY, parent_id INT, FOREIGN KEY(parent_id) REFERENCES legacy_parent(id))')
            connection.execute(text('INSERT INTO legacy_parent (id,label,payload,amount,raw_bytes,created_at) VALUES (1,:label,:payload,12.34,:raw_bytes,:created_at)'),
                               {'label': "Tiếng Việt ' \\ \n 🙂", 'payload': json.dumps({'education': 'giáo dục'}),
                                'raw_bytes': b'\x00\xff\x80\x27', 'created_at': '2026-10-19 01:02:03'})
            connection.exec_driver_sql('INSERT INTO legacy_child VALUES (1,1)')
            connection.execute(User.__table__.insert().values(username='retained', email='retained@example.com', password_hash='test-hash'))
            original = connection.exec_driver_sql('SELECT * FROM legacy_parent').all()
        report = prepare_database(mysql_config, Base.metadata, tmp_path)
        assert report.created_tables == ('citations',)
        assert set(report.removed_tables) == {'legacy_parent', 'legacy_child'}
        assert report.backup_path.is_file() and not list(tmp_path.glob('*.partial'))
        with engine.connect() as connection:
            assert set(inspect(connection).get_table_names()) == set(Base.metadata.tables)
            assert connection.exec_driver_sql('SELECT username FROM users').scalar_one() == 'retained'
        # Restore the dump within this disposable database, including binary,
        # JSON, Unicode, generated columns and foreign-key dependency order.
        restore = create_engine(mysql_url(mysql_config, mysql_config.DB_NAME), isolation_level='AUTOCOMMIT',
                                connect_args={'client_flag': CLIENT.MULTI_STATEMENTS})
        try:
            with restore.connect() as connection:
                cursor = connection.connection.driver_connection.cursor()
                try:
                    cursor.execute(report.backup_path.read_text(encoding='utf-8'))
                    while cursor.nextset():
                        pass
                finally:
                    cursor.close()
                assert connection.exec_driver_sql('SELECT * FROM legacy_parent').all() == original
                assert connection.exec_driver_sql('SELECT parent_id FROM legacy_child').scalar_one() == 1
        finally:
            restore.dispose()
    finally:
        engine.dispose()


def test_backup_failure_leaves_missing_and_extra_tables_untouched(mysql_config, tmp_path, monkeypatch):
    prepare_database(mysql_config, Base.metadata, tmp_path)
    engine = create_engine(mysql_url(mysql_config, mysql_config.DB_NAME))
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql('DROP TABLE citations')
            connection.exec_driver_sql('CREATE TABLE legacy_extra (id INT PRIMARY KEY)')
            connection.exec_driver_sql('INSERT INTO legacy_extra VALUES (77)')
        def fail_backup(*args):
            raise PermissionError('Backup directory not writable')
        monkeypatch.setattr('app.db.bootstrap.backup_tables', fail_backup)
        with pytest.raises(PermissionError):
            prepare_database(mysql_config, Base.metadata, tmp_path)
        with engine.connect() as connection:
            assert 'citations' not in inspect(connection).get_table_names()
            assert connection.exec_driver_sql('SELECT id FROM legacy_extra').scalar_one() == 77
            assert connection.exec_driver_sql('SELECT @@SESSION.FOREIGN_KEY_CHECKS').scalar_one() == 1
    finally:
        engine.dispose()


def test_retained_table_reference_blocks_dropping_extra_table(mysql_config, tmp_path):
    prepare_database(mysql_config, Base.metadata, tmp_path)
    engine = create_engine(mysql_url(mysql_config, mysql_config.DB_NAME))
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql('CREATE TABLE legacy_extra (id INT PRIMARY KEY)')
            connection.exec_driver_sql('ALTER TABLE users ADD legacy_id INT, ADD FOREIGN KEY (legacy_id) REFERENCES legacy_extra(id)')
        with pytest.raises(RuntimeError, match='khóa ngoại'):
            prepare_database(mysql_config, Base.metadata, tmp_path)
        with engine.connect() as connection:
            assert 'legacy_extra' in inspect(connection).get_table_names()
        assert not list(tmp_path.iterdir())
    finally:
        engine.dispose()
