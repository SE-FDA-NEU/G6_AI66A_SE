"""Prepare and verify the configured MySQL database separately from API startup.

Models own the six-table application schema. Existing application tables are
never rebuilt. By default, extra/shared tables in the target schema are
preserved (never dropped), and any schema change backs up existing tables first.
This is table creation and verification, not automatic column/type migration.
"""
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import build_ssl_context

DESIGN_TABLES = ('users', 'folders', 'documents', 'jobs', 'job_files', 'citations')


@dataclass(frozen=True)
class DatabaseReport:
    created_database: bool
    created_tables: tuple[str, ...]
    removed_tables: tuple[str, ...]
    backup_path: Path | None
    preserved_extra_tables: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectionDiagnostics:
    dialect: str
    database: str | None
    charset_ok: bool
    tls_enabled: bool
    ssl_version: str | None
    ssl_cipher: str | None
    permissions_ok: bool
    grants_summary: tuple[str, ...]


def mysql_url(config, database=None):
    # URL.create handles passwords/usernames containing @, /, #, %, etc.
    return URL.create('mysql+pymysql', username=config.DB_USER,
                      password=config.DB_PASSWORD, host=config.DB_HOST,
                      port=int(config.DB_PORT), database=database,
                      query={'charset': 'utf8mb4'})


def mysql_connect_args(config) -> dict[str, Any]:
    if hasattr(config, 'db_connect_args'):
        return dict(config.db_connect_args)
    connect_timeout = int(getattr(config, 'DB_CONNECT_TIMEOUT_SECONDS', 10))
    read_timeout = int(getattr(config, 'DB_READ_TIMEOUT_SECONDS', 30))
    write_timeout = int(getattr(config, 'DB_WRITE_TIMEOUT_SECONDS', 30))
    ssl_mode = getattr(config, 'DB_SSL_MODE', 'preferred')
    args: dict[str, Any] = {
        'charset': 'utf8mb4',
        'connect_timeout': connect_timeout,
        'read_timeout': read_timeout,
        'write_timeout': write_timeout,
    }
    if ssl_mode == 'disabled':
        args['ssl_disabled'] = True
    else:
        ssl_ctx = build_ssl_context(
            ssl_mode=ssl_mode,
            ssl_ca=getattr(config, 'DB_SSL_CA', ''),
            ssl_cert=getattr(config, 'DB_SSL_CERT', ''),
            ssl_key=getattr(config, 'DB_SSL_KEY', ''),
            ssl_verify_cert=getattr(config, 'DB_SSL_VERIFY_CERT', None),
            ssl_verify_identity=getattr(config, 'DB_SSL_VERIFY_IDENTITY', None),
        )
        if ssl_ctx is not None:
            args['ssl'] = ssl_ctx
    return args


def backup_tables(connection, names, directory):
    """Write a restorable SQL snapshot; finish/fsync it before permitting DDL.

    Driver-level rows retain JSON strings and native dates/decimals. Binary
    columns use hex so the UTF-8 dump never corrupts bytes. Do not log row data.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = directory / f'schema-{stamp}-{uuid4().hex[:8]}.sql'
    partial = target.with_suffix('.sql.partial')
    quote = connection.dialect.identifier_preparer.quote_identifier
    driver = connection.connection.driver_connection
    descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    escape_cursor = driver.cursor()
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as handle:
            mode = connection.exec_driver_sql('SELECT @@SESSION.sql_mode').scalar_one()
            sql_mode = escape_cursor.mogrify('%s', (mode,))
            if isinstance(sql_mode, bytes):
                sql_mode = sql_mode.decode('utf-8')
            handle.write('-- DocuMind table backup. Restore into the intended database with the app stopped.\n')
            handle.write('SET NAMES utf8mb4;\nSET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS;\nSET FOREIGN_KEY_CHECKS=0;\n')
            handle.write(f'SET @OLD_SQL_MODE=@@SQL_MODE;\nSET SQL_MODE={sql_mode};\n')
            for name in sorted(names):
                quoted = quote(name)
                ddl = connection.exec_driver_sql(f'SHOW CREATE TABLE {quoted}').one()[1]
                handle.write(f'\nDROP TABLE IF EXISTS {quoted};\n{ddl};\n')
                ordinary = [column['name'] for column in inspect(connection).get_columns(name) if not column.get('computed')]
                projection = ', '.join(quote(column) for column in ordinary) or '1 AS _row'
                rows = connection.execution_options(stream_results=True).exec_driver_sql(f'SELECT {projection} FROM {quoted}')
                try:
                    columns = ', '.join(quote(column) for column in ordinary)
                    for row in rows:
                        rendered = []
                        for value in row:
                            if isinstance(value, bytes):
                                rendered.append('0x' + value.hex() if value else "X''")
                            else:
                                literal = escape_cursor.mogrify('%s', (value,))
                                if isinstance(literal, bytes):
                                    literal = literal.decode('utf-8')
                                rendered.append(str(literal))
                        values = ', '.join(rendered) if ordinary else ''
                        handle.write(f'INSERT INTO {quoted} ({columns}) VALUES ({values});\n')
                finally:
                    rows.close()
                    connection.execution_options(stream_results=False)
            handle.write('\nSET SQL_MODE=@OLD_SQL_MODE;\nSET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;\n')
            handle.flush()
            os.fsync(handle.fileno())
        partial.rename(target)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    finally:
        escape_cursor.close()
    return target


def verify_schema(connection, metadata) -> dict[str, Any]:
    """Verify that all six authoritative tables, columns and FKs match models."""
    inspector = inspect(connection)
    names = set(inspector.get_table_names())
    views = set(inspector.get_view_names())
    expected = set(metadata.tables)
    if expected & views:
        raise RuntimeError('Tên bảng trong models đang bị một view sử dụng. Hãy đổi tên view trước.')
    missing_tables = sorted(expected - names)
    if missing_tables:
        raise RuntimeError('Thiếu bảng theo models: ' + ', '.join(missing_tables))

    for name in sorted(expected):
        model_table = metadata.tables[name]
        actual_columns = {col['name'] for col in inspector.get_columns(name)}
        expected_columns = set(model_table.columns.keys())
        missing_columns = sorted(expected_columns - actual_columns)
        if missing_columns:
            raise RuntimeError(
                f'Bảng {name} thiếu cột theo models: {", ".join(missing_columns)}. '
                'Bootstrap không tự động migrate cột; hãy sao lưu và chạy ALTER TABLE trước.'
            )
        pk = set(inspector.get_pk_constraint(name).get('constrained_columns') or ())
        expected_pk = {col.name for col in model_table.primary_key.columns}
        if pk != expected_pk:
            raise RuntimeError(f'Khóa chính của bảng {name} không khớp models.')
        actual_fks = {
            (tuple(fk.get('constrained_columns') or ()), fk.get('referred_table'))
            for fk in inspector.get_foreign_keys(name)
        }
        expected_fks = {
            ((fk.parent.name,), fk.column.table.name)
            for fk in model_table.foreign_keys
        }
        if not expected_fks.issubset(actual_fks):
            raise RuntimeError(f'Khóa ngoại của bảng {name} không khớp models.')

    if connection.dialect.name == 'mysql':
        db_charset = connection.execute(
            text('SELECT DEFAULT_CHARACTER_SET_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = DATABASE()')
        ).scalar_one_or_none()
        if db_charset and not str(db_charset).lower().startswith('utf8mb4'):
            raise RuntimeError(f'Database đang dùng charset {db_charset}, cần utf8mb4.')
        non_utf8mb4 = connection.execute(text('''
            SELECT TABLE_NAME, TABLE_COLLATION
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_TYPE = 'BASE TABLE'
              AND TABLE_NAME IN :tables
              AND TABLE_COLLATION IS NOT NULL
              AND LOWER(TABLE_COLLATION) NOT LIKE 'utf8mb4%'
        '''), {'tables': tuple(sorted(expected))}).all()
        if non_utf8mb4:
            bad = ', '.join(f'{tbl} ({coll})' for tbl, coll in non_utf8mb4)
            raise RuntimeError(f'Các bảng chưa dùng collation utf8mb4: {bad}.')

    return {
        'verified_tables': tuple(sorted(expected)),
        'extra_tables': tuple(sorted(names - expected)),
    }


def check_connection_health(connection, config=None) -> ConnectionDiagnostics:
    """Check connection liveness, UTF8MB4 charset, TLS state and DB permissions."""
    one = connection.execute(text('SELECT 1')).scalar_one()
    if one != 1:
        raise RuntimeError('Kiểm tra kết nối SELECT 1 không hợp lệ.')
    dialect = connection.dialect.name
    if dialect != 'mysql':
        return ConnectionDiagnostics(
            dialect=dialect,
            database=None,
            charset_ok=True,
            tls_enabled=False,
            ssl_version=None,
            ssl_cipher=None,
            permissions_ok=True,
            grants_summary=('LOCAL_DIALECT',),
        )

    database = connection.exec_driver_sql('SELECT DATABASE()').scalar_one()
    charsets = connection.exec_driver_sql(
        'SELECT @@character_set_client, @@character_set_connection, @@character_set_results'
    ).one()
    charset_ok = all(value and str(value).lower().startswith('utf8mb4') for value in charsets)
    if not charset_ok:
        raise RuntimeError(f'Kết nối MySQL chưa dùng utf8mb4: {charsets}.')

    cipher_row = connection.exec_driver_sql("SHOW SESSION STATUS LIKE 'Ssl_cipher'").first()
    version_row = connection.exec_driver_sql("SHOW SESSION STATUS LIKE 'Ssl_version'").first()
    ssl_cipher = str(cipher_row[1]).strip() if cipher_row and cipher_row[1] else None
    ssl_version = str(version_row[1]).strip() if version_row and version_row[1] else None
    tls_enabled = bool(ssl_cipher)

    ssl_mode = getattr(config, 'DB_SSL_MODE', 'preferred') if config is not None else 'preferred'
    if ssl_mode in ('required', 'verify_ca', 'verify_identity') and not tls_enabled:
        raise RuntimeError('Cấu hình yêu cầu kết nối TLS (DB_SSL_MODE) nhưng phiên MySQL chưa được mã hóa.')

    raw_grants = [str(row[0]) for row in connection.exec_driver_sql('SHOW GRANTS FOR CURRENT_USER()').all()]
    sanitized_grants = tuple(
        grant.split(' IDENTIFIED BY ', 1)[0] for grant in raw_grants
    )
    upper_grants = ' '.join(sanitized_grants).upper()
    required_privs = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'INDEX', 'REFERENCES')
    permissions_ok = (
        'ALL PRIVILEGES' in upper_grants
        or all(priv in upper_grants for priv in required_privs)
    )
    if not permissions_ok:
        raise RuntimeError('Tài khoản MySQL thiếu quyền bắt buộc trên schema ứng dụng.')

    return ConnectionDiagnostics(
        dialect=dialect,
        database=database,
        charset_ok=charset_ok,
        tls_enabled=tls_enabled,
        ssl_version=ssl_version,
        ssl_cipher=ssl_cipher,
        permissions_ok=permissions_ok,
        grants_summary=sanitized_grants,
    )


def verify_reconnection(engine) -> bool:
    """Verify pool_pre_ping recovers cleanly after a dropped/invalidated connection."""
    if not getattr(engine.pool, '_pre_ping', False):
        raise RuntimeError('SQLAlchemy engine chưa bật pool_pre_ping để tự kết nối lại.')
    with engine.connect() as first_conn:
        assert first_conn.execute(text('SELECT 1')).scalar_one() == 1
        first_conn.invalidate()
    with engine.connect() as recovered_conn:
        assert recovered_conn.execute(text('SELECT 1')).scalar_one() == 1
    return True


def sync_tables(connection, metadata, backup_directory, *, remove_extra_tables=False):
    inspector = inspect(connection)
    names = set(inspector.get_table_names())
    expected = set(metadata.tables)
    missing, extra = expected - names, names - expected
    # Never create a model table over a view of the same name.
    if missing & set(inspector.get_view_names()):
        raise RuntimeError('Tên bảng trong models đang bị một view sử dụng. Hãy đổi tên view trước.')
    for name in names & expected:
        model_table = metadata.tables[name]
        actual_columns = {col['name'] for col in inspector.get_columns(name)}
        missing_columns = sorted(set(model_table.columns.keys()) - actual_columns)
        if missing_columns:
            raise RuntimeError(
                f'Bảng {name} thiếu cột theo models: {", ".join(missing_columns)}. '
                'Bootstrap không tự động migrate cột; hãy sao lưu và chạy ALTER TABLE trước.'
            )
        if remove_extra_tables and any(fk['referred_table'] in extra for fk in inspector.get_foreign_keys(name)):
            raise RuntimeError(f'Bảng {name} đang tham chiếu bảng thừa; cần sửa khóa ngoại trước khi đồng bộ.')
    if remove_extra_tables and extra:
        # MySQL foreign-key checks must not be bypassed for another database.
        incoming = connection.execute(text('''
            SELECT TABLE_SCHEMA, TABLE_NAME, REFERENCED_TABLE_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE REFERENCED_TABLE_SCHEMA = DATABASE()
        ''')).all()
        database = connection.exec_driver_sql('SELECT DATABASE()').scalar_one()
        if any(parent in extra and (schema != database or child not in extra)
               for schema, child, parent in incoming):
            raise RuntimeError('Có bảng được giữ lại hoặc database khác tham chiếu bảng thừa; chưa thay đổi database.')
    needs_ddl = bool(missing or (remove_extra_tables and extra))
    backup = backup_tables(connection, names, backup_directory) if names and needs_ddl else None
    removed = ()
    try:
        if remove_extra_tables and extra:
            old_checks = connection.exec_driver_sql('SELECT @@SESSION.FOREIGN_KEY_CHECKS').scalar_one()
            try:
                connection.exec_driver_sql('SET SESSION FOREIGN_KEY_CHECKS=0')
                quote = connection.dialect.identifier_preparer.quote_identifier
                for name in sorted(extra):
                    connection.exec_driver_sql(f'DROP TABLE {quote(name)}')
                removed = tuple(sorted(extra))
            finally:
                connection.exec_driver_sql(f'SET SESSION FOREIGN_KEY_CHECKS={int(old_checks)}')
        if missing:
            metadata.create_all(connection, tables=[metadata.tables[name] for name in sorted(missing)])
        else:
            metadata.create_all(connection)
        current_tables = set(inspect(connection).get_table_names())
        if remove_extra_tables:
            if current_tables != expected:
                raise RuntimeError('Danh sách bảng sau đồng bộ không khớp models.')
        elif not expected.issubset(current_tables):
            raise RuntimeError('Thiếu bảng của models sau khi đồng bộ.')
        verify_schema(connection, metadata)
    except Exception as error:
        suffix = f' Bản sao lưu: {backup}' if backup else ''
        raise RuntimeError(f'Không thể hoàn tất đồng bộ bảng.{suffix}') from error
    return tuple(sorted(missing)), removed, backup


def _sync_with_lock(control, target_engine, db_name, metadata, backup_directory, remove_extra_tables, created_database):
    lock_name = 'documind-schema-' + hashlib.sha256(db_name.encode()).hexdigest()[:40]
    locked = control.execute(text('SELECT GET_LOCK(:name, 15)'), {'name': lock_name}).scalar_one()
    if locked != 1:
        raise RuntimeError('Một tiến trình khác đang đồng bộ database. Hãy thử chạy lại.')
    try:
        with target_engine.connect() as connection:
            before_extra = set(inspect(connection).get_table_names()) - set(metadata.tables)
            created, removed, backup = sync_tables(
                connection,
                metadata,
                backup_directory,
                remove_extra_tables=remove_extra_tables,
            )
            preserved = () if remove_extra_tables else tuple(sorted(before_extra))
        return DatabaseReport(created_database, created, removed, backup, preserved)
    finally:
        control.execute(text('SELECT RELEASE_LOCK(:name)'), {'name': lock_name})


def prepare_database(config, metadata, backup_directory, *, remove_extra_tables=None):
    drop_extra = (
        bool(getattr(config, 'DB_DROP_EXTRA_TABLES', False))
        if remove_extra_tables is None
        else bool(remove_extra_tables)
    )
    connect_args = mysql_connect_args(config)
    admin = create_engine(mysql_url(config), isolation_level='AUTOCOMMIT',
                          connect_args=connect_args)
    target = None
    try:
        try:
            with admin.connect() as control:
                lock_name = 'documind-schema-' + hashlib.sha256(config.DB_NAME.encode()).hexdigest()[:40]
                locked = control.execute(text('SELECT GET_LOCK(:name, 15)'), {'name': lock_name}).scalar_one()
                if locked != 1:
                    raise RuntimeError('Một tiến trình khác đang đồng bộ database. Hãy thử chạy lại.')
                try:
                    exists = control.execute(
                        text('SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=:name'),
                        {'name': config.DB_NAME},
                    ).scalar_one_or_none()
                    if exists is None:
                        name = control.dialect.identifier_preparer.quote_identifier(config.DB_NAME)
                        control.exec_driver_sql(f'CREATE DATABASE {name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
                    target = create_engine(mysql_url(config, config.DB_NAME), isolation_level='AUTOCOMMIT',
                                           connect_args=connect_args)
                    with target.connect() as connection:
                        before_extra = set(inspect(connection).get_table_names()) - set(metadata.tables)
                        created, removed, backup = sync_tables(
                            connection,
                            metadata,
                            backup_directory,
                            remove_extra_tables=drop_extra,
                        )
                        preserved = () if drop_extra else tuple(sorted(before_extra))
                    return DatabaseReport(exists is None, created, removed, backup, preserved)
                finally:
                    control.execute(text('SELECT RELEASE_LOCK(:name)'), {'name': lock_name})
        except SQLAlchemyError as admin_error:
            code = getattr(admin_error.orig, 'args', [None])[0] if hasattr(admin_error, 'orig') else None
            if code not in (1044, 1045, 1142, 1227):
                raise
            # Cloud MySQL accounts are often scoped exclusively to the pre-created DB_NAME.
            target = create_engine(mysql_url(config, config.DB_NAME), isolation_level='AUTOCOMMIT',
                                   connect_args=connect_args)
            with target.connect() as control:
                return _sync_with_lock(
                    control,
                    target,
                    config.DB_NAME,
                    metadata,
                    backup_directory,
                    drop_extra,
                    False,
                )
    except SQLAlchemyError as error:
        # SQLAlchemy exception strings can include connection parameters and SQL.
        code = getattr(error.orig, 'args', [None])[0] if hasattr(error, 'orig') else None
        message = ('Sai tài khoản/mật khẩu MySQL hoặc tài khoản thiếu quyền.' if code in (1044, 1045, 1142, 1227)
                   else 'Không kết nối hoặc chuẩn bị được MySQL. Kiểm tra MySQL đang bật và DB_HOST/DB_PORT trong backend/.env.')
        raise RuntimeError(f'{message} Mã lỗi: {code or "database_error"}.') from None
    finally:
        if target is not None:
            target.dispose()
        admin.dispose()


def backup_database(config, backup_directory, *, tables=None) -> Path | None:
    """Create an explicit restorable SQL backup before manual schema/column changes."""
    target = create_engine(mysql_url(config, config.DB_NAME), isolation_level='AUTOCOMMIT',
                           connect_args=mysql_connect_args(config))
    try:
        with target.connect() as connection:
            existing = set(inspect(connection).get_table_names())
            selected = sorted(existing & set(tables)) if tables is not None else sorted(existing)
            if not selected:
                return None
            return backup_tables(connection, selected, backup_directory)
    except SQLAlchemyError as error:
        code = getattr(error.orig, 'args', [None])[0] if hasattr(error, 'orig') else None
        raise RuntimeError(f'Không thể sao lưu database. Mã lỗi: {code or "database_error"}.') from None
    finally:
        target.dispose()


def verify_database(config, metadata) -> tuple[ConnectionDiagnostics, dict[str, Any]]:
    """Verify connection, TLS, permissions, pool reconnection and six-table schema without DDL."""
    from app.db.database import create_mysql_engine
    engine = create_mysql_engine(config) if hasattr(config, 'engine_options') else create_engine(
        mysql_url(config, config.DB_NAME),
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args=mysql_connect_args(config),
    )
    try:
        verify_reconnection(engine)
        with engine.connect() as connection:
            diagnostics = check_connection_health(connection, config)
            schema_info = verify_schema(connection, metadata)
            return diagnostics, schema_info
    except SQLAlchemyError as error:
        code = getattr(error.orig, 'args', [None])[0] if hasattr(error, 'orig') else None
        raise RuntimeError(f'Không thể xác minh database. Mã lỗi: {code or "database_error"}.') from None
    finally:
        engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Prepare, back up or verify the DocuMind MySQL schema.')
    parser.add_argument('--verify-only', action='store_true',
                        help='Verify connection, TLS, permissions, reconnection and six-table schema without DDL.')
    parser.add_argument('--backup-only', action='store_true',
                        help='Write a SQL backup snapshot before manual schema or column migrations.')
    parser.add_argument('--drop-extra-tables', action='store_true',
                        help='Back up and drop non-model tables (disabled by default to protect shared databases).')
    args = parser.parse_args(argv)

    from app.core.config import settings
    from app.db.database import Base
    import app.models  # noqa: F401 — populate the authoritative metadata
    root = Path(__file__).resolve().parents[2]
    backup_dir = root / 'data' / 'backups'

    if args.backup_only:
        backup_path = backup_database(settings, backup_dir)
        if backup_path:
            print(f'Đã tạo bản sao lưu SQL: {backup_path}', flush=True)
        else:
            print('Database chưa có bảng nào để sao lưu.', flush=True)
        return

    if args.verify_only:
        diagnostics, schema_info = verify_database(settings, Base.metadata)
        tls_label = f'{diagnostics.ssl_version} ({diagnostics.ssl_cipher})' if diagnostics.tls_enabled else 'chưa bật'
        print(f'Kết nối MySQL hợp lệ (utf8mb4, TLS: {tls_label}, pool_pre_ping: OK).', flush=True)
        if schema_info['extra_tables']:
            print('Bảng dùng chung được giữ nguyên: ' + ', '.join(schema_info['extra_tables']), flush=True)
        print(f'Schema hợp lệ: đúng {len(schema_info["verified_tables"])} bảng theo models.', flush=True)
        return

    report = prepare_database(
        settings,
        Base.metadata,
        backup_dir,
        remove_extra_tables=True if args.drop_extra_tables else None,
    )
    print('Database: ' + ('đã tạo mới.' if report.created_database else 'đã tồn tại.'))
    if report.backup_path:
        print(f'Đã sao lưu trước khi thay đổi bảng: {report.backup_path}', flush=True)
    if report.created_tables:
        print('Đã tạo bảng thiếu: ' + ', '.join(report.created_tables))
    if report.removed_tables:
        print('Đã bỏ bảng thừa: ' + ', '.join(report.removed_tables))
    if report.preserved_extra_tables:
        print('Đã giữ nguyên bảng dùng chung/ngoài models: ' + ', '.join(report.preserved_extra_tables))
    print(f'Database sẵn sàng: đúng {len(Base.metadata.tables)} bảng theo models.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        from pydantic import ValidationError
        if isinstance(error, ValidationError):
            print('backend/.env chưa hợp lệ. Kiểm tra các trường: ' + ', '.join(str(e['loc'][0]) for e in error.errors()))
        elif isinstance(error, RuntimeError):
            print(str(error))
        else:
            print('Không thể kiểm tra database. Kiểm tra backend/.env và quyền của tài khoản MySQL.')
        raise SystemExit(1) from None
