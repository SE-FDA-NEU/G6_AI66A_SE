"""Cloud MySQL configuration, six-table schema, Vietnamese/JSON/enums, TLS/permissions/reconnection and safe bootstrap tests."""
from datetime import datetime, timedelta
from pathlib import Path
import ssl
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import Settings, build_ssl_context
from app.core.security import create_access_token
from app.db.bootstrap import (
    DESIGN_TABLES,
    check_connection_health,
    mysql_connect_args,
    mysql_url,
    prepare_database,
    sync_tables,
    verify_reconnection,
    verify_schema,
)
from app.db.database import Base, create_mysql_engine, engine as runtime_engine
from app.models import (
    Citation,
    Document,
    FileFormat,
    Folder,
    Job,
    JobFile,
    JobMode,
    JobStatus,
    ReviewState,
    User,
)


def test_cloud_mysql_config_builds_pymysql_utf8mb4_url_and_tls_pool_options():
    cfg = Settings(
        DB_USER="cloud_user",
        DB_PASSWORD="p@ss:w/rd#123%?",
        DB_HOST="mysql-prod.cloud.example.com",
        DB_PORT="25060",
        DB_NAME="documind_cloud",
        DB_SSL_MODE="verify_identity",
        DB_CONNECT_TIMEOUT_SECONDS=15,
        DB_READ_TIMEOUT_SECONDS=45,
        DB_WRITE_TIMEOUT_SECONDS=45,
        DB_POOL_PRE_PING=True,
        DB_POOL_RECYCLE_SECONDS=900,
        DB_POOL_SIZE=8,
        DB_MAX_OVERFLOW=12,
        DB_POOL_TIMEOUT_SECONDS=20,
        SECRET_KEY="test-secret-key",
    )
    url = mysql_url(cfg, cfg.DB_NAME)
    assert url.drivername == "mysql+pymysql"
    assert url.host == "mysql-prod.cloud.example.com"
    assert url.port == 25060
    assert url.database == "documind_cloud"
    assert url.username == "cloud_user"
    assert url.password == "p@ss:w/rd#123%?"
    assert dict(url.query) == {"charset": "utf8mb4"}
    assert "charset=utf8mb4" in cfg.DATABASE_URL

    opts = cfg.engine_options
    assert opts["pool_pre_ping"] is True
    assert opts["pool_recycle"] == 900
    assert opts["pool_size"] == 8
    assert opts["max_overflow"] == 12
    assert opts["pool_timeout"] == 20
    assert cfg.DB_DROP_EXTRA_TABLES is False

    connect_args = opts["connect_args"]
    assert connect_args["charset"] == "utf8mb4"
    assert connect_args["connect_timeout"] == 15
    assert connect_args["read_timeout"] == 45
    assert connect_args["write_timeout"] == 45
    assert isinstance(connect_args["ssl"], ssl.SSLContext)
    assert connect_args["ssl"].verify_mode == ssl.CERT_REQUIRED
    assert connect_args["ssl"].check_hostname is True

    test_engine = create_mysql_engine(cfg)
    try:
        assert test_engine.pool._pre_ping is True
        assert test_engine.pool._recycle == 900
    finally:
        test_engine.dispose()

    assert runtime_engine.pool._pre_ping is True


def test_tls_modes_disabled_preferred_required_and_verify_ca():
    assert build_ssl_context("disabled") is None
    assert build_ssl_context("preferred") is None

    required_ctx = build_ssl_context("required")
    assert isinstance(required_ctx, ssl.SSLContext)
    assert required_ctx.verify_mode == ssl.CERT_NONE
    assert required_ctx.check_hostname is False

    verify_ca_ctx = build_ssl_context("verify_ca")
    assert isinstance(verify_ca_ctx, ssl.SSLContext)
    assert verify_ca_ctx.verify_mode == ssl.CERT_REQUIRED
    assert verify_ca_ctx.check_hostname is False

    ns_disabled = SimpleNamespace(
        DB_USER="u",
        DB_PASSWORD="p",
        DB_HOST="localhost",
        DB_PORT="3306",
        DB_NAME="d",
        DB_SSL_MODE="disabled",
    )
    assert mysql_connect_args(ns_disabled)["ssl_disabled"] is True


def test_verify_schema_checks_six_tables_columns_and_detects_unmigrated_columns():
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        with engine.connect() as conn:
            info = verify_schema(conn, Base.metadata)
            assert info["verified_tables"] == tuple(sorted(DESIGN_TABLES))
            assert info["extra_tables"] == ()

        # Simulate an older schema missing a newly added column on documents.
        drifted_engine = create_engine("sqlite://")
        try:
            with drifted_engine.begin() as conn:
                for name in DESIGN_TABLES:
                    if name != "documents":
                        Base.metadata.tables[name].create(conn)
                conn.exec_driver_sql(
                    "CREATE TABLE documents ("
                    "id INTEGER PRIMARY KEY, "
                    "owner_id INTEGER NOT NULL REFERENCES users(id), "
                    "original_filename VARCHAR(255) NOT NULL)"
                )
            with drifted_engine.connect() as conn:
                with pytest.raises(RuntimeError, match="Bảng documents thiếu cột theo models"):
                    verify_schema(conn, Base.metadata)
        finally:
            drifted_engine.dispose()
    finally:
        engine.dispose()


def test_vietnamese_text_json_enums_relationships_and_ownership(session_factory, client):
    now = datetime.utcnow()
    vietnamese_text_pages = [
        {
            "page": 1,
            "text": "Hợp đồng chuyển nhượng quyền sử dụng đất số 01/2026/HĐ-CN tại Hà Nội. Giá trị: 1.200.000.000 VNĐ.",
            "positions": [{"char": 0, "x0": 36.0, "y0": 720.0}],
        },
        {
            "page": 2,
            "text": "Điều khoản phạt chậm thanh toán 0,05%/ngày — Nghị định 13/2023/NĐ-CP bảo vệ dữ liệu cá nhân.",
        },
    ]
    vietnamese_result_data = {
        "language": "vi",
        "summary": "Tóm tắt tiếng Việt đầy đủ dấu: Đặng Vũ, Nguyễn Bảo Tài, Tô Hiển Hải Đăng, Bùi Đăng Dương.",
        "documents": {
            "1": {
                "language": "vi",
                "output": {
                    "bullets": ["Điều khoản thanh toán trong vòng 30 ngày kể từ ngày nghiệm thu."],
                    "actions": ["Kiểm tra bảo lãnh ngân hàng trước khi giải ngân đợt 1."],
                },
            }
        },
    }

    with session_factory() as db:
        folder_a = Folder(owner_id=123, name="Hồ sơ Pháp lý & Hợp đồng Quý 4")
        folder_b = Folder(owner_id=124, name="Tài liệu riêng của người dùng B")
        db.add_all([folder_a, folder_b])
        db.flush()

        doc_a = Document(
            owner_id=123,
            folder_id=folder_a.id,
            original_filename="Hợp_đồng_thuê_nhà_Đống_Đa_2026.pdf",
            storage_path="/storage/123/hop_dong_thue_nha.pdf",
            file_format=FileFormat.PDF,
            file_size_bytes=524288,
            page_count=2,
            ai_label="Hợp đồng pháp lý",
            ai_confidence=0.92,
            review_state=ReviewState.CONFIRMED,
            user_label="Đã duyệt nội bộ",
            extracted_text=vietnamese_text_pages,
            last_accessed_at=now,
            expires_at=now + timedelta(days=30),
        )
        doc_docx = Document(
            owner_id=123,
            folder_id=None,
            original_filename="Báo_cáo_tài_chính_năm.docx",
            storage_path="/storage/123/bao_cao.docx",
            file_format=FileFormat.DOCX,
            file_size_bytes=262144,
            page_count=5,
            ai_label="Tài chính kế toán",
            ai_confidence=0.74,
            review_state=ReviewState.NEEDS_REVIEW,
            user_label=None,
            extracted_text=[{"page": 1, "text": "Doanh thu thuần đạt 25 tỷ đồng."}],
            last_accessed_at=now,
            expires_at=now + timedelta(days=30),
        )
        doc_b = Document(
            owner_id=124,
            folder_id=folder_b.id,
            original_filename="Tài_liệu_mật_của_B.pptx",
            storage_path="/storage/124/bi_mat.pptx",
            file_format=FileFormat.PPTX,
            file_size_bytes=131072,
            page_count=10,
            ai_label="Chiến lược",
            ai_confidence=0.88,
            review_state=ReviewState.CONFIRMED,
            user_label="Chiến lược B",
            extracted_text=[{"page": 1, "text": "Nội dung độc quyền của tài khoản B."}],
            last_accessed_at=now,
            expires_at=now + timedelta(days=30),
        )
        db.add_all([doc_a, doc_docx, doc_b])
        db.flush()

        job_a = Job(
            owner_id=123,
            mode=JobMode.BULLET,
            status=JobStatus.COMPLETED,
            file_count=2,
            completed_count=2,
            result_data=vietnamese_result_data,
            finished_at=now,
        )
        job_b = Job(
            owner_id=124,
            mode=JobMode.TABLE,
            status=JobStatus.TIMED_OUT,
            file_count=1,
            completed_count=0,
            result_data=None,
        )
        db.add_all([job_a, job_b])
        db.flush()

        jf_a1 = JobFile(
            job_id=job_a.id,
            document_id=doc_a.id,
            status=JobStatus.COMPLETED,
            attempt_count=1,
            timeout_seconds=36,
        )
        jf_a2 = JobFile(
            job_id=job_a.id,
            document_id=doc_docx.id,
            status=JobStatus.FAILED,
            attempt_count=2,
            timeout_seconds=45,
            error_message="Quá thời gian phản hồi từ dịch vụ phân tích tiếng Việt.",
        )
        cite_a = Citation(
            job_id=job_a.id,
            document_id=doc_a.id,
            claim_text="Giá trị chuyển nhượng là 1.200.000.000 VNĐ.",
            doc_name=doc_a.original_filename,
            page=1,
            text_span="Giá trị: 1.200.000.000 VNĐ.",
            unverified=False,
        )
        db.add_all([jf_a1, jf_a2, cite_a])
        db.commit()

        doc_a_id, doc_docx_id, doc_b_id = doc_a.id, doc_docx.id, doc_b.id
        folder_a_id, folder_b_id = folder_a.id, folder_b.id
        job_a_id, job_b_id = job_a.id, job_b.id

    # Verify round-trip of Vietnamese strings, JSON structures and Enums
    with session_factory() as db:
        saved_doc = db.get(Document, doc_a_id)
        assert saved_doc.original_filename == "Hợp_đồng_thuê_nhà_Đống_Đa_2026.pdf"
        assert saved_doc.file_format is FileFormat.PDF
        assert saved_doc.review_state is ReviewState.CONFIRMED
        assert saved_doc.extracted_text == vietnamese_text_pages
        assert saved_doc.folder.name == "Hồ sơ Pháp lý & Hợp đồng Quý 4"

        saved_job = db.get(Job, job_a_id)
        assert saved_job.mode is JobMode.BULLET
        assert saved_job.status is JobStatus.COMPLETED
        assert saved_job.result_data["summary"].startswith("Tóm tắt tiếng Việt đầy đủ dấu:")
        assert len(saved_job.job_files) == 2
        assert len(saved_job.citations) == 1
        assert saved_job.citations[0].claim_text == "Giá trị chuyển nhượng là 1.200.000.000 VNĐ."

    # Verify API ownership isolation (BR07) between User 123 and User 124
    resp_docs = client.get("/documents", params={"ai_label": "Hợp đồng pháp lý"})
    assert resp_docs.status_code == 200
    assert [d["id"] for d in resp_docs.json()] == [doc_a_id]

    assert client.get(f"/documents/{doc_b_id}").status_code == 403
    assert client.patch(f"/documents/{doc_a_id}/folder", json={"folder_id": folder_b_id}).status_code == 403
    assert client.get(f"/jobs/{job_b_id}").status_code == 404

    other_headers = {"Authorization": f"Bearer {create_access_token({'sub': '124'})}"}
    assert client.get(f"/documents/{doc_a_id}", headers=other_headers).status_code == 403
    assert client.get(f"/jobs/{job_a_id}", headers=other_headers).status_code == 404

    # Verify FK cascades: deleting a folder sets documents.folder_id = NULL without deleting documents
    with session_factory() as db:
        db.execute(text("DELETE FROM folders WHERE id = :id"), {"id": folder_a_id})
        db.commit()
        reloaded_doc = db.get(Document, doc_a_id)
        assert reloaded_doc is not None
        assert reloaded_doc.folder_id is None

        # Deleting a document cascades to its citations and job_files
        db.execute(text("DELETE FROM documents WHERE id = :id"), {"id": doc_a_id})
        db.commit()
        assert db.query(Citation).filter_by(document_id=doc_a_id).count() == 0
        assert db.query(JobFile).filter_by(document_id=doc_a_id).count() == 0
        assert db.get(Document, doc_docx_id) is not None


def test_default_sync_tables_preserves_shared_tables_and_backs_up_before_changes(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    try:
        # Create 5 of the 6 model tables + 1 shared non-model table
        with engine.begin() as conn:
            for name in DESIGN_TABLES:
                if name != "citations":
                    Base.metadata.tables[name].create(conn)
            conn.exec_driver_sql("CREATE TABLE shared_billing_audit (id INTEGER PRIMARY KEY, description TEXT)")
            conn.exec_driver_sql("INSERT INTO shared_billing_audit VALUES (1, 'shared-row')")

        backup_calls = []

        def fake_backup(connection, names, directory):
            backup_calls.append(tuple(sorted(names)))
            target = Path(directory) / "schema-backup.sql"
            target.write_text("-- backup\n", encoding="utf-8")
            return target

        monkeypatch.setattr("app.db.bootstrap.backup_tables", fake_backup)

        with engine.begin() as conn:
            created, removed, backup = sync_tables(conn, Base.metadata, tmp_path)
            assert created == ("citations",)
            assert removed == ()
            assert backup == tmp_path / "schema-backup.sql"
            assert len(backup_calls) == 1
            assert "shared_billing_audit" in backup_calls[0]

            all_tables = set(inspect(conn).get_table_names())
            assert set(DESIGN_TABLES).issubset(all_tables)
            assert "shared_billing_audit" in all_tables
            assert conn.exec_driver_sql("SELECT description FROM shared_billing_audit WHERE id = 1").scalar_one() == "shared-row"
    finally:
        engine.dispose()


def test_check_connection_health_verifies_tls_charset_and_permissions():
    mock_conn = MagicMock()
    mock_conn.dialect.name = "mysql"
    mock_conn.execute.return_value.scalar_one.return_value = 1

    def side_effect_driver_sql(sql):
        result = MagicMock()
        if "SELECT DATABASE()" in sql:
            result.scalar_one.return_value = "documind_cloud"
        elif "@@character_set_client" in sql:
            result.one.return_value = ("utf8mb4", "utf8mb4", "utf8mb4")
        elif "Ssl_cipher" in sql:
            result.first.return_value = ("Ssl_cipher", "TLS_AES_256_GCM_SHA384")
        elif "Ssl_version" in sql:
            result.first.return_value = ("Ssl_version", "TLSv1.3")
        elif "SHOW GRANTS" in sql:
            result.all.return_value = [
                ("GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES ON `documind_cloud`.* TO `app`@`%`",)
            ]
        return result

    mock_conn.exec_driver_sql.side_effect = side_effect_driver_sql
    cfg = SimpleNamespace(DB_SSL_MODE="verify_identity")
    diag = check_connection_health(mock_conn, cfg)
    assert diag.charset_ok is True
    assert diag.tls_enabled is True
    assert diag.ssl_version == "TLSv1.3"
    assert diag.ssl_cipher == "TLS_AES_256_GCM_SHA384"
    assert diag.permissions_ok is True

    # If TLS is required but Ssl_cipher is empty, check_connection_health must reject the connection
    def unencrypted_driver_sql(sql):
        result = MagicMock()
        if "SELECT DATABASE()" in sql:
            result.scalar_one.return_value = "documind_cloud"
        elif "@@character_set_client" in sql:
            result.one.return_value = ("utf8mb4", "utf8mb4", "utf8mb4")
        elif "Ssl_cipher" in sql or "Ssl_version" in sql:
            result.first.return_value = ("Ssl_cipher", "")
        return result

    mock_conn.exec_driver_sql.side_effect = unencrypted_driver_sql
    with pytest.raises(RuntimeError, match="TLS"):
        check_connection_health(mock_conn, cfg)


def test_pool_pre_ping_reconnection_recovers_after_connection_invalidation(tmp_path):
    db_file = tmp_path / "reconnect.sqlite"
    engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        poolclass=QueuePool,
        pool_pre_ping=True,
        pool_recycle=600,
    )
    try:
        assert verify_reconnection(engine) is True
    finally:
        engine.dispose()


def test_api_startup_is_separate_from_schema_bootstrap(client, monkeypatch):
    def forbidden_bootstrap(*args, **kwargs):
        raise AssertionError("API startup must not run schema bootstrap or DDL")

    monkeypatch.setattr("app.db.bootstrap.prepare_database", forbidden_bootstrap)
    monkeypatch.setattr("app.db.bootstrap.sync_tables", forbidden_bootstrap)
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json() == {"message": "Welcome to DocuMind API"}


def test_bootstrap_cli_modes_verify_only_backup_only_and_default_safe_sync(tmp_path, monkeypatch, capsys):
    from app.db import bootstrap

    called = {}

    def fake_backup_database(config, backup_dir, *, tables=None):
        called["backup"] = backup_dir
        return tmp_path / "manual-backup.sql"

    def fake_verify_database(config, metadata):
        called["verify"] = True
        diag = bootstrap.ConnectionDiagnostics(
            dialect="mysql",
            database="documind_cloud",
            charset_ok=True,
            tls_enabled=True,
            ssl_version="TLSv1.3",
            ssl_cipher="TLS_AES_256_GCM_SHA384",
            permissions_ok=True,
            grants_summary=("GRANT SELECT, INSERT ON `documind_cloud`.*",),
        )
        return diag, {"verified_tables": tuple(sorted(DESIGN_TABLES)), "extra_tables": ("shared_audit",)}

    def fake_prepare_database(config, metadata, backup_dir, *, remove_extra_tables=None):
        called["prepare"] = remove_extra_tables
        return bootstrap.DatabaseReport(
            created_database=False,
            created_tables=(),
            removed_tables=(),
            backup_path=None,
            preserved_extra_tables=("shared_audit",),
        )

    monkeypatch.setattr(bootstrap, "backup_database", fake_backup_database)
    monkeypatch.setattr(bootstrap, "verify_database", fake_verify_database)
    monkeypatch.setattr(bootstrap, "prepare_database", fake_prepare_database)

    bootstrap.main(["--backup-only"])
    out_backup = capsys.readouterr().out
    assert "manual-backup.sql" in out_backup

    bootstrap.main(["--verify-only"])
    out_verify = capsys.readouterr().out
    assert "TLSv1.3" in out_verify
    assert "shared_audit" in out_verify

    bootstrap.main([])
    out_default = capsys.readouterr().out
    assert called["prepare"] is None
    assert "Đã giữ nguyên bảng dùng chung/ngoài models: shared_audit" in out_default

