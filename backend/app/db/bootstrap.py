"""Prepare the configured local MySQL database before application workers start.

Models own the table list. Existing application tables are never rebuilt; every
extra table is backed up with all existing table DDL/data before it is removed.
This is table synchronization, not automatic column/type migration.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError


@dataclass(frozen=True)
class DatabaseReport:
    created_database: bool
    created_tables: tuple[str, ...]
    removed_tables: tuple[str, ...]
    backup_path: Path | None


def mysql_url(config, database=None):
    # URL.create handles passwords/usernames containing @, /, #, %, etc.
    return URL.create('mysql+pymysql', username=config.DB_USER,
                      password=config.DB_PASSWORD, host=config.DB_HOST,
                      port=int(config.DB_PORT), database=database,
                      query={'charset': 'utf8mb4'})


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


def sync_tables(connection, metadata, backup_directory):
    inspector = inspect(connection)
    names = set(inspector.get_table_names())
    expected = set(metadata.tables)
    missing, extra = expected - names, names - expected
    # Never create a model table over a view of the same name.
    if missing & set(inspector.get_view_names()):
        raise RuntimeError('Tên bảng trong models đang bị một view sử dụng. Hãy đổi tên view trước.')
    for name in names & expected:
        if any(fk['referred_table'] in extra for fk in inspector.get_foreign_keys(name)):
            raise RuntimeError(f'Bảng {name} đang tham chiếu bảng thừa; cần sửa khóa ngoại trước khi đồng bộ.')
    if extra:
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
    backup = backup_tables(connection, names, backup_directory) if names and (missing or extra) else None
    try:
        if extra:
            old_checks = connection.exec_driver_sql('SELECT @@SESSION.FOREIGN_KEY_CHECKS').scalar_one()
            try:
                connection.exec_driver_sql('SET SESSION FOREIGN_KEY_CHECKS=0')
                quote = connection.dialect.identifier_preparer.quote_identifier
                for name in sorted(extra):
                    connection.exec_driver_sql(f'DROP TABLE {quote(name)}')
            finally:
                connection.exec_driver_sql(f'SET SESSION FOREIGN_KEY_CHECKS={int(old_checks)}')
        metadata.create_all(connection)
        if set(inspect(connection).get_table_names()) != expected:
            raise RuntimeError('Danh sách bảng sau đồng bộ không khớp models.')
    except Exception as error:
        suffix = f' Bản sao lưu: {backup}' if backup else ''
        raise RuntimeError(f'Không thể hoàn tất đồng bộ bảng.{suffix}') from error
    return tuple(sorted(missing)), tuple(sorted(extra)), backup


def prepare_database(config, metadata, backup_directory):
    admin = create_engine(mysql_url(config), isolation_level='AUTOCOMMIT',
                          connect_args={'connect_timeout': 10})
    target = None
    try:
        with admin.connect() as control:
            lock_name = 'documind-schema-' + hashlib.sha256(config.DB_NAME.encode()).hexdigest()[:40]
            locked = control.execute(text('SELECT GET_LOCK(:name, 15)'), {'name': lock_name}).scalar_one()
            if locked != 1:
                raise RuntimeError('Một tiến trình khác đang đồng bộ database. Hãy thử chạy lại.')
            try:
                exists = control.execute(text('SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=:name'),
                                         {'name': config.DB_NAME}).scalar_one_or_none()
                if exists is None:
                    name = control.dialect.identifier_preparer.quote_identifier(config.DB_NAME)
                    control.exec_driver_sql(f'CREATE DATABASE {name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
                target = create_engine(mysql_url(config, config.DB_NAME), isolation_level='AUTOCOMMIT',
                                       connect_args={'connect_timeout': 10})
                with target.connect() as connection:
                    created, removed, backup = sync_tables(connection, metadata, backup_directory)
                return DatabaseReport(exists is None, created, removed, backup)
            finally:
                control.execute(text('SELECT RELEASE_LOCK(:name)'), {'name': lock_name})
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


def main():
    from app.core.config import settings
    from app.db.database import Base
    import app.models  # noqa: F401 — populate the authoritative metadata
    root = Path(__file__).resolve().parents[2]
    report = prepare_database(settings, Base.metadata, root / 'data' / 'backups')
    print('Database: ' + ('đã tạo mới.' if report.created_database else 'đã tồn tại.'))
    if report.backup_path:
        print(f'Đã sao lưu trước khi thay đổi bảng: {report.backup_path}', flush=True)
    if report.created_tables:
        print('Đã tạo bảng thiếu: ' + ', '.join(report.created_tables))
    if report.removed_tables:
        print('Đã bỏ bảng thừa: ' + ', '.join(report.removed_tables))
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
