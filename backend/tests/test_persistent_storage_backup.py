"""Tests for persistent STORAGE_DIR, path validation/migration, restart persistence, and coordinated backup/restore."""
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.main import app
from app.models import Citation, Document, Job, User
from app.schemas.result import AnalysisResult, Claim, Evidence, TableOutput
from app.services import processing, retention_cleanup as cleanup
from app.services.job_queue import get_job_queue
from app.services.storage_ops import (
    create_coordinated_backup,
    ensure_writable_storage,
    main as storage_ops_main,
    migrate_storage_paths,
    resolve_owner_relative_path,
    restore_coordinated_backup,
    validate_storage_paths,
)
from test_pdf_extraction import make_pdf


def _make_isolated_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)


def test_ensure_writable_storage_creates_root_and_analysis_cache(tmp_path):
    storage_root = tmp_path / "persistent-mount" / "uploads"
    resolved = ensure_writable_storage(storage_root)
    assert resolved == storage_root.resolve()
    assert resolved.is_dir()
    assert (resolved / ".analysis-cache").is_dir()


def test_resolve_and_migrate_stored_paths_across_windows_and_linux_mounts(
    client, session_factory, tmp_path, monkeypatch
):
    pdf_source = make_pdf(
        tmp_path / "contract.pdf",
        [b"BT /F1 12 Tf 36 720 Td (Contract value: 2,500,000,000 VND) Tj ET"],
    )
    upload = client.post(
        "/upload",
        data={"mode": "table"},
        files=[("files", ("contract-migrate.pdf", pdf_source.read_bytes(), "application/pdf"))],
    )
    assert upload.status_code == 202
    job_id = int(upload.json()["jobId"])

    async def analyze(document, mode):
        page = document.extracted_text[0]
        quote = page["text"]
        claim = Claim(
            text="2,500,000,000 VND",
            unverified=False,
            evidence=[
                Evidence(
                    document_id=document.id,
                    page=1,
                    start=0,
                    end=len(quote),
                    quote=quote,
                    reader_version=page["reader"]["sha256"],
                )
            ],
        )
        return AnalysisResult(output=TableOutput(value=claim))

    processing.process_job(job_id, session_factory, analyzer=analyze)

    with session_factory() as db:
        doc = db.query(Document).filter_by(owner_id=123).one()
        doc_id = doc.id
        rel = Path(doc.storage_path).resolve().relative_to(settings.STORAGE_DIR.resolve())
        # Simulate a stored Windows path from another machine before volume relocation
        simulated_windows_path = f"C:\\DocuMind\\old_uploads\\{str(rel).replace('/', chr(92))}"
        doc.storage_path = simulated_windows_path
        db.commit()

    assert resolve_owner_relative_path(simulated_windows_path, 123).parts == rel.parts

    before_validation = validate_storage_paths(session_factory, settings.STORAGE_DIR)
    assert not before_validation.ok
    assert doc_id in before_validation.outside_root_ids

    dry_preview = migrate_storage_paths(session_factory, settings.STORAGE_DIR, dry_run=True)
    assert dry_preview.migrated_document_ids == (doc_id,)
    assert dry_preview.dry_run is True

    migrated = migrate_storage_paths(session_factory, settings.STORAGE_DIR, dry_run=False)
    assert migrated.migrated_document_ids == (doc_id,)
    assert not migrated.unresolved_document_ids

    after_validation = validate_storage_paths(session_factory, settings.STORAGE_DIR)
    assert after_validation.ok
    assert after_validation.valid_document_ids == (doc_id,)
    assert len(after_validation.valid_citation_ids) == 1


def test_reader_citations_search_and_cache_survive_restart_and_coordinated_restore(
    client, session_factory, job_queue, tmp_path, monkeypatch
):
    pdf_source = make_pdf(
        tmp_path / "persistent-source.pdf",
        [b"BT /F1 12 Tf 36 720 Td (PersistentClause 1,200,000,000 VND penalty 0.05%) Tj ET"],
    )
    upload = client.post(
        "/upload",
        data={"mode": "table"},
        files=[
            ("files", ("active-contract.pdf", pdf_source.read_bytes(), "application/pdf")),
            ("files", ("expiring-contract.pdf", pdf_source.read_bytes(), "application/pdf")),
        ],
    )
    assert upload.status_code == 202
    job_id = int(upload.json()["jobId"])

    async def analyze(document, mode):
        page = document.extracted_text[0]
        quote = page["text"]
        claim = Claim(
            text="1,200,000,000 VND",
            unverified=False,
            evidence=[
                Evidence(
                    document_id=document.id,
                    page=1,
                    start=0,
                    end=len(quote),
                    quote=quote,
                    reader_version=page["reader"]["sha256"],
                )
            ],
        )
        return AnalysisResult(output=TableOutput(value=claim))

    processing.process_job(job_id, session_factory, analyzer=analyze)

    # Create an analysis cache entry for owner 123
    owner_cache = settings.STORAGE_DIR / ".analysis-cache" / "123"
    owner_cache.mkdir(parents=True, exist_ok=True)
    (owner_cache / "cached-wire.json").write_text('{"cached": true}', encoding="utf-8")

    with session_factory() as db:
        docs = db.query(Document).filter_by(owner_id=123).order_by(Document.id).all()
        active_id, expired_id = docs[0].id, docs[1].id
        # Expire only the second document in a separate standalone state
        expired_doc = db.get(Document, expired_id)
        expired_doc.storage_path = "expired:/removed/path.pdf"
        expired_doc.extracted_text = None
        expired_doc.file_size_bytes = 0
        db.query(Citation).filter_by(document_id=expired_id).delete(synchronize_session=False)
        db.commit()

    # 1. Verify survival across simulated API restart (new TestClient instance with same DB & STORAGE_DIR)
    with TestClient(app) as restarted_client:
        restarted_client.headers["Authorization"] = f"Bearer {create_access_token({'sub': '123'})}"
        pages_resp = restarted_client.get(f"/documents/{active_id}/pages")
        assert pages_resp.status_code == 200
        reader_url = pages_resp.json()["reader_url"]
        reader_version = pages_resp.json()["reader_version"]

        pdf_resp = restarted_client.get(reader_url)
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["x-reader-version"] == reader_version

        highlight_resp = restarted_client.get(
            f"/documents/{active_id}/reader.pdf",
            params={"version": reader_version, "highlight_page": 1, "q": "PersistentClause"},
        )
        assert highlight_resp.status_code == 200

        search_resp = restarted_client.get("/search", params={"q": "PersistentClause"})
        assert search_resp.status_code == 200
        assert search_resp.json()["total_hits"] == 1
        assert search_resp.json()["hits"][0]["document_id"] == active_id

        job_resp = restarted_client.get(f"/jobs/{job_id}")
        assert job_resp.status_code == 200
        assert any(c["document_id"] == active_id for c in job_resp.json()["citations"])

    # 2. Create coordinated backup (DB + matching STORAGE_DIR files)
    backup_root = tmp_path / "backups"
    bundle_dir = create_coordinated_backup(session_factory, settings.STORAGE_DIR, backup_root)
    assert (bundle_dir / "manifest.json").is_file()
    assert (bundle_dir / "tables.json").is_file()
    assert (bundle_dir / "storage.tar.gz").is_file()

    # In-place restore to the exact same live STORAGE_DIR must be rejected by default
    with pytest.raises(ValueError, match="separate target STORAGE_DIR"):
        restore_coordinated_backup(bundle_dir, session_factory, settings.STORAGE_DIR)

    # 3. Restore into a completely separate database and separate target STORAGE_DIR
    restored_engine, restored_factory = _make_isolated_db()
    restored_storage = tmp_path / "restored-volume" / "uploads"
    try:
        report = restore_coordinated_backup(bundle_dir, restored_factory, restored_storage)
        assert report.ok
        assert report.valid_document_ids == (active_id,)
        assert report.expired_document_ids == (expired_id,)
        assert len(report.valid_citation_ids) >= 1
        assert (restored_storage / ".analysis-cache" / "123" / "cached-wire.json").is_file()

        # Mount the restored DB and restored STORAGE_DIR in the API and verify reader/citations/410
        def restored_db_dep():
            with restored_factory() as db:
                yield db

        monkeypatch.setattr(settings, "STORAGE_DIR", restored_storage)
        app.dependency_overrides[get_db] = restored_db_dep
        with TestClient(app) as restored_client:
            restored_client.headers["Authorization"] = f"Bearer {create_access_token({'sub': '123'})}"
            r_pages = restored_client.get(f"/documents/{active_id}/pages")
            assert r_pages.status_code == 200
            r_pdf = restored_client.get(r_pages.json()["reader_url"])
            assert r_pdf.status_code == 200
            assert r_pdf.content.startswith(b"%PDF")

            r_search = restored_client.get("/search", params={"q": "PersistentClause"})
            assert r_search.status_code == 200
            assert r_search.json()["total_hits"] == 1

            # Expired tombstone remains 410 Gone after restoration (never resurrected)
            r_expired = restored_client.get(f"/documents/{expired_id}/file")
            assert r_expired.status_code == 410
    finally:
        restored_engine.dispose()


def test_storage_ops_cli_verify_backup_and_restore_test(client, session_factory, tmp_path, monkeypatch, capsys):
    pdf_source = make_pdf(
        tmp_path / "cli.pdf",
        [b"BT /F1 12 Tf 36 720 Td (CLI backup verification text) Tj ET"],
    )
    upload = client.post(
        "/upload",
        data={"mode": "bullet"},
        files=[("files", ("cli.pdf", pdf_source.read_bytes(), "application/pdf"))],
    )
    assert upload.status_code == 202
    job_id = int(upload.json()["jobId"])
    processing.process_job(job_id, session_factory)

    backup_dir = tmp_path / "cli-backups"
    monkeypatch.setattr(settings, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr("app.db.database.SessionLocal", session_factory)

    storage_ops_main(["--verify"])
    assert "writable=True" in capsys.readouterr().out

    storage_ops_main(["--backup"])
    backup_out = capsys.readouterr().out
    assert "Đã tạo bản sao lưu đồng bộ" in backup_out
    bundles = list(backup_dir.iterdir())
    assert len(bundles) == 1

    storage_ops_main(["--restore-test", str(bundles[0])])
    restore_out = capsys.readouterr().out
    assert "Khôi phục thử nghiệm thành công tại môi trường tách biệt" in restore_out
