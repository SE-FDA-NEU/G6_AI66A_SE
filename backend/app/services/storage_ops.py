"""Persistent STORAGE_DIR verification, path validation/migration, and coordinated DB + file backup/restore.

Preserves the existing filesystem flow:
- Originals:       <STORAGE_DIR>/<owner_id>/<batch_or_file>
- Reader PDFs:     <Path(storage_path).parent>/.reader/<document_id>/<sha256>.pdf
- Analysis cache:  <STORAGE_DIR>/.analysis-cache/<owner_id>/<sha256>.json
"""
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tarfile
import tempfile
from typing import Any
from uuid import uuid4

from sqlalchemy import inspect

from app.core.config import settings
from app.db.bootstrap import DESIGN_TABLES, backup_tables
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
from app.services.document_retention import EXPIRED_PATH_PREFIX, is_expired_source
from app.services.reader_extraction import ReaderConversionError, reader_file, reader_representation, sha256


@dataclass(frozen=True)
class StorageValidationReport:
    storage_root: Path
    writable: bool
    valid_document_ids: tuple[int, ...]
    expired_document_ids: tuple[int, ...]
    outside_root_ids: tuple[int, ...]
    missing_original_ids: tuple[int, ...]
    missing_reader_ids: tuple[int, ...]
    hash_mismatch_ids: tuple[int, ...]
    valid_citation_ids: tuple[int, ...]
    broken_citation_ids: tuple[int, ...]

    @property
    def ok(self) -> bool:
        return (
            self.writable
            and not self.outside_root_ids
            and not self.missing_original_ids
            and not self.missing_reader_ids
            and not self.hash_mismatch_ids
            and not self.broken_citation_ids
        )


@dataclass(frozen=True)
class PathMigrationReport:
    migrated_document_ids: tuple[int, ...]
    unchanged_document_ids: tuple[int, ...]
    expired_document_ids: tuple[int, ...]
    unresolved_document_ids: tuple[int, ...]
    dry_run: bool


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    if path.exists():
        attrs = getattr(path.lstat(), "st_file_attributes", 0)
        if attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            return True
    return False


def ensure_writable_storage(storage_root: Path | str | None = None) -> Path:
    """Verify STORAGE_DIR and .analysis-cache exist, are writable, and support atomic replace."""
    raw_root = Path(storage_root if storage_root is not None else settings.STORAGE_DIR)
    if _is_link_or_reparse(raw_root):
        raise RuntimeError("STORAGE_DIR must not be a symlink or reparse point.")
    raw_root.mkdir(parents=True, exist_ok=True)
    root = raw_root.resolve()
    if _is_link_or_reparse(root):
        raise RuntimeError("Resolved STORAGE_DIR must not be a symlink or reparse point.")

    cache_dir = root / ".analysis-cache"
    if _is_link_or_reparse(cache_dir):
        raise RuntimeError("STORAGE_DIR/.analysis-cache must not be a symlink or reparse point.")
    cache_dir.mkdir(parents=True, exist_ok=True)

    for directory in (root, cache_dir):
        staged = None
        target = directory / f".write-probe-{uuid4().hex}.tmp"
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".probe-",
                suffix=".tmp",
                dir=directory,
                delete=False,
            ) as handle:
                staged = Path(handle.name)
                handle.write(b"documind-storage-probe")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(staged, target)
            if target.read_bytes() != b"documind-storage-probe":
                raise RuntimeError(f"Storage probe verification failed in {directory}.")
        except OSError as error:
            raise RuntimeError(f"STORAGE_DIR is not writable or does not support atomic replace: {directory}") from error
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
    return root


def _checked_storage_target(candidate: Path, root: Path) -> Path:
    root = root.resolve()
    abs_candidate = candidate.absolute()
    if not abs_candidate.is_relative_to(root) or abs_candidate == root:
        raise ValueError("Target path is outside STORAGE_DIR.")
    for part in (abs_candidate, *abs_candidate.parents):
        if part == root:
            break
        if _is_link_or_reparse(part):
            raise ValueError("Target path contains a symlink or reparse point.")
    resolved = abs_candidate.resolve()
    if not resolved.is_relative_to(root) or resolved == root:
        raise ValueError("Resolved target path escapes STORAGE_DIR.")
    return resolved


def resolve_owner_relative_path(raw_path: str, owner_id: int, old_root: str | Path | None = None) -> PurePosixPath | None:
    """Extract a safe <owner_id>/... relative path from a stored Windows or POSIX path."""
    if not raw_path or raw_path.startswith(EXPIRED_PATH_PREFIX):
        return None
    normalized = raw_path.replace("\\", "/").strip()
    owner_token = str(owner_id)

    if old_root is not None:
        old_norm = str(old_root).replace("\\", "/").rstrip("/")
        if normalized.startswith(old_norm + "/"):
            tail = normalized[len(old_norm) + 1 :]
            rel = PurePosixPath(tail)
            if ".." not in rel.parts and rel.parts and rel.parts[0] == owner_token and len(rel.parts) >= 2:
                return rel

    parts = [part for part in PurePosixPath(normalized).parts if part not in ("", "/")]
    if ".." in parts:
        return None
    # Match the last occurrence of /<owner_id>/<file> or /<owner_id>/<batch>/<file>
    for index in range(len(parts) - 2, -1, -1):
        if parts[index] == owner_token:
            subparts = parts[index:]
            if 2 <= len(subparts) <= 3:
                return PurePosixPath(*subparts)
    # Fallback: if the stored path is a legacy seed path like /storage/demouser/filename.pdf,
    # map it to <owner_id>/<filename> when that file exists on the target.
    if parts:
        filename = parts[-1]
        if filename and filename not in (".", ".."):
            return PurePosixPath(owner_token, filename)
    return None


def validate_storage_paths(session_factory, storage_root: Path | str | None = None) -> StorageValidationReport:
    """Validate stored document paths, .reader PDFs, SHA-256 hashes and citations."""
    try:
        root = ensure_writable_storage(storage_root)
        writable = True
    except RuntimeError:
        root = Path(storage_root if storage_root is not None else settings.STORAGE_DIR).resolve()
        writable = False

    valid_docs: list[int] = []
    expired_docs: list[int] = []
    outside_root: list[int] = []
    missing_originals: list[int] = []
    missing_readers: list[int] = []
    hash_mismatches: list[int] = []
    valid_citations: list[int] = []
    broken_citations: list[int] = []

    with session_factory() as db:
        documents = db.query(Document).order_by(Document.id).all()
        doc_by_id = {doc.id: doc for doc in documents}
        for doc in documents:
            if is_expired_source(doc):
                expired_docs.append(doc.id)
                continue
            owner_root = root / str(doc.owner_id)
            source = Path(doc.storage_path)
            try:
                checked_source = _checked_storage_target(source, owner_root)
            except ValueError:
                outside_root.append(doc.id)
                continue
            if not checked_source.is_file():
                missing_originals.append(doc.id)
                continue

            pages = doc.extracted_text
            if isinstance(pages, list) and pages and isinstance(pages[0], dict) and isinstance(pages[0].get("reader"), dict):
                try:
                    r_path, reference = reader_representation(doc)
                    _checked_storage_target(r_path, owner_root)
                except (ReaderConversionError, ValueError) as error:
                    code = getattr(error, "code", "")
                    if code == "reader_file_unavailable":
                        r_candidate = reader_file(doc, pages[0]["reader"])
                        if not r_candidate.is_file():
                            missing_readers.append(doc.id)
                        else:
                            hash_mismatches.append(doc.id)
                    else:
                        hash_mismatches.append(doc.id)
                    continue
                if sha256(checked_source) != reference.get("source_sha256"):
                    hash_mismatches.append(doc.id)
                    continue

            valid_docs.append(doc.id)

        valid_doc_set = set(valid_docs)
        for citation in db.query(Citation).order_by(Citation.id).all():
            doc = doc_by_id.get(citation.document_id)
            if doc is None or doc.id not in valid_doc_set:
                broken_citations.append(citation.id)
                continue
            if citation.page is not None:
                if doc.page_count is None or not (1 <= citation.page <= doc.page_count):
                    broken_citations.append(citation.id)
                    continue
            valid_citations.append(citation.id)

    return StorageValidationReport(
        storage_root=root,
        writable=writable,
        valid_document_ids=tuple(valid_docs),
        expired_document_ids=tuple(expired_docs),
        outside_root_ids=tuple(outside_root),
        missing_original_ids=tuple(missing_originals),
        missing_reader_ids=tuple(missing_readers),
        hash_mismatch_ids=tuple(hash_mismatches),
        valid_citation_ids=tuple(valid_citations),
        broken_citation_ids=tuple(broken_citations),
    )


def migrate_storage_paths(
    session_factory,
    storage_root: Path | str | None = None,
    *,
    old_root: Path | str | None = None,
    dry_run: bool = False,
) -> PathMigrationReport:
    """Validate or migrate Document.storage_path to the target STORAGE_DIR without breaking .reader links."""
    root = ensure_writable_storage(storage_root)
    migrated: list[int] = []
    unchanged: list[int] = []
    expired: list[int] = []
    unresolved: list[int] = []

    with session_factory() as db:
        documents = db.query(Document).order_by(Document.id).with_for_update().all()
        for doc in documents:
            if is_expired_source(doc):
                expired.append(doc.id)
                continue
            owner_root = root / str(doc.owner_id)
            current_path = Path(doc.storage_path)
            try:
                checked_current = _checked_storage_target(current_path, owner_root)
                if checked_current.is_file() and str(checked_current) == doc.storage_path:
                    unchanged.append(doc.id)
                    continue
            except ValueError:
                pass

            rel = resolve_owner_relative_path(doc.storage_path, doc.owner_id, old_root=old_root)
            if rel is None:
                unresolved.append(doc.id)
                continue
            candidate = root.joinpath(*rel.parts)
            try:
                checked_target = _checked_storage_target(candidate, owner_root)
            except ValueError:
                unresolved.append(doc.id)
                continue
            if not checked_target.is_file():
                unresolved.append(doc.id)
                continue

            pages = doc.extracted_text
            if isinstance(pages, list) and pages and isinstance(pages[0], dict) and isinstance(pages[0].get("reader"), dict):
                ref = pages[0]["reader"]
                expected_source_sha = ref.get("source_sha256")
                expected_reader_sha = ref.get("sha256")
                expected_reader = checked_target.parent / ".reader" / str(doc.id) / f"{expected_reader_sha}.pdf"
                if (
                    not expected_source_sha
                    or sha256(checked_target) != expected_source_sha
                    or not expected_reader.is_file()
                    or sha256(expected_reader) != expected_reader_sha
                ):
                    unresolved.append(doc.id)
                    continue

            if not dry_run:
                doc.storage_path = str(checked_target)
            migrated.append(doc.id)

        if not dry_run:
            db.commit()
        else:
            db.rollback()

    return PathMigrationReport(
        migrated_document_ids=tuple(migrated),
        unchanged_document_ids=tuple(unchanged),
        expired_document_ids=tuple(expired),
        unresolved_document_ids=tuple(unresolved),
        dry_run=dry_run,
    )


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    if hasattr(value, "value"):
        return value.value
    return value


def _deserialize_row(model_cls, row: dict[str, Any]) -> dict[str, Any]:
    enum_map = {
        "file_format": FileFormat,
        "review_state": ReviewState,
        "mode": JobMode,
        "status": JobStatus,
    }
    restored: dict[str, Any] = {}
    for key, val in row.items():
        if isinstance(val, dict) and "__datetime__" in val:
            restored[key] = datetime.fromisoformat(val["__datetime__"])
        elif key in enum_map and val is not None:
            restored[key] = enum_map[key](val)
        else:
            restored[key] = val
    return restored


def create_coordinated_backup(
    session_factory,
    storage_root: Path | str | None = None,
    backup_dir: Path | str | None = None,
) -> Path:
    """Back up all six database tables (SQL on MySQL + portable JSON) and matching STORAGE_DIR files."""
    root = ensure_writable_storage(storage_root)
    base_backup_dir = Path(backup_dir if backup_dir is not None else settings.BACKUP_DIR).resolve()
    base_backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    bundle_dir = base_backup_dir / f"coordinated-{stamp}-{uuid4().hex[:8]}"
    bundle_dir.mkdir(parents=True, exist_ok=False, mode=0o700)

    models_in_order = [
        ("users", User),
        ("folders", Folder),
        ("documents", Document),
        ("jobs", Job),
        ("job_files", JobFile),
        ("citations", Citation),
    ]
    tables_payload: dict[str, list[dict[str, Any]]] = {}
    file_hashes: dict[str, str] = {}
    sql_dump_name: str | None = None

    with session_factory() as db:
        bind = db.get_bind()
        if bind.dialect.name == "mysql":
            with bind.connect() as conn:
                existing_tables = sorted(set(inspect(conn).get_table_names()) & set(DESIGN_TABLES))
                if existing_tables:
                    sql_path = backup_tables(conn, existing_tables, bundle_dir)
                    sql_dump_name = sql_path.name

        for table_name, model_cls in models_in_order:
            rows = db.query(model_cls).order_by(model_cls.id).all()
            cols = [col.name for col in model_cls.__table__.columns]
            tables_payload[table_name] = [
                {col: _serialize_value(getattr(item, col)) for col in cols}
                for item in rows
            ]

    tables_file = bundle_dir / "tables.json"
    tables_file.write_text(
        json.dumps({"tables": tables_payload}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    archive_path = bundle_dir / "storage.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        for item in sorted(root.rglob("*")):
            if item.name.startswith(".write-probe-") or item.name.startswith(".probe-"):
                continue
            if _is_link_or_reparse(item):
                raise RuntimeError(f"Refusing to archive symlink or reparse point: {item}")
            rel = item.relative_to(root).as_posix()
            tar.add(item, arcname=rel, recursive=False)
            if item.is_file():
                file_hashes[rel] = sha256(item)

    manifest = {
        "schema_version": 1,
        "created_at": stamp,
        "source_storage_root": str(root),
        "sql_dump": sql_dump_name,
        "table_counts": {name: len(rows) for name, rows in tables_payload.items()},
        "file_hashes": file_hashes,
    }
    (bundle_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return bundle_dir


def _safe_extract_tar(archive_path: Path, destination: Path) -> None:
    destination = destination.resolve()
    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            if member.issym() or member.islnk() or member.isdev():
                raise ValueError(f"Archive contains unsupported link or device entry: {member.name}")
            rel = PurePosixPath(member.name)
            if rel.is_absolute() or ".." in rel.parts:
                raise ValueError(f"Archive entry escapes target root: {member.name}")
            target = (destination / Path(*rel.parts)).resolve()
            if not target.is_relative_to(destination):
                raise ValueError(f"Resolved archive entry escapes target root: {member.name}")
        tar.extractall(destination, filter="data")


def restore_coordinated_backup(
    bundle_dir: Path | str,
    target_session_factory,
    target_storage_root: Path | str,
    *,
    allow_same_root: bool = False,
) -> StorageValidationReport:
    """Restore a coordinated backup into a separate target DB + STORAGE_DIR and verify reader/citations."""
    bundle = Path(bundle_dir).resolve()
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    tables_data = json.loads((bundle / "tables.json").read_text(encoding="utf-8"))["tables"]
    source_root = Path(manifest["source_storage_root"]).resolve()
    target_root = ensure_writable_storage(target_storage_root)

    if not allow_same_root and target_root == source_root:
        raise ValueError("Restore verification must use a separate target STORAGE_DIR from the live source root.")

    _safe_extract_tar(bundle / "storage.tar.gz", target_root)

    for rel_str, expected_hash in manifest.get("file_hashes", {}).items():
        extracted_file = target_root / Path(*PurePosixPath(rel_str).parts)
        if not extracted_file.is_file() or sha256(extracted_file) != expected_hash:
            raise RuntimeError(f"Restored file checksum mismatch for {rel_str}.")

    models_in_order = [
        ("users", User),
        ("folders", Folder),
        ("documents", Document),
        ("jobs", Job),
        ("job_files", JobFile),
        ("citations", Citation),
    ]
    with target_session_factory() as db:
        for _, model_cls in reversed(models_in_order):
            db.query(model_cls).delete(synchronize_session=False)
        for table_name, model_cls in models_in_order:
            for raw_row in tables_data.get(table_name, []):
                db.add(model_cls(**_deserialize_row(model_cls, raw_row)))
        db.commit()

    migration = migrate_storage_paths(
        target_session_factory,
        target_root,
        old_root=source_root,
        dry_run=False,
    )
    if migration.unresolved_document_ids:
        raise RuntimeError(f"Could not resolve restored paths for documents: {migration.unresolved_document_ids}")

    validation = validate_storage_paths(target_session_factory, target_root)
    if not validation.ok:
        raise RuntimeError(f"Restored storage validation failed: {validation}")
    return validation


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify STORAGE_DIR, migrate stored paths, or run coordinated backup/restore.")
    parser.add_argument("--verify", action="store_true", help="Verify STORAGE_DIR writability, stored paths, .reader PDFs and citations.")
    parser.add_argument("--migrate-paths", action="store_true", help="Migrate stored Document.storage_path entries to current STORAGE_DIR.")
    parser.add_argument("--old-root", type=str, default=None, help="Optional previous STORAGE_DIR prefix when migrating across hosts/OS.")
    parser.add_argument("--dry-run", action="store_true", help="Preview path migrations without modifying the database.")
    parser.add_argument("--backup", action="store_true", help="Create a coordinated database + STORAGE_DIR backup bundle.")
    parser.add_argument("--restore-test", type=Path, default=None, help="Test restoring a backup bundle into a separate temporary environment.")
    args = parser.parse_args(argv)

    from app.db.database import Base, SessionLocal
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    if args.restore_test is not None:
        with tempfile.TemporaryDirectory(prefix="documind-restore-test-") as temp_dir:
            temp_root = Path(temp_dir) / "uploads"
            engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

            @event.listens_for(engine, "connect")
            def _fk(conn, _):
                conn.execute("PRAGMA foreign_keys=ON")

            Base.metadata.create_all(engine)
            test_factory = sessionmaker(bind=engine)
            try:
                report = restore_coordinated_backup(args.restore_test, test_factory, temp_root)
                print(
                    f"Khôi phục thử nghiệm thành công tại môi trường tách biệt: "
                    f"{len(report.valid_document_ids)} tài liệu hợp lệ, "
                    f"{len(report.valid_citation_ids)} trích dẫn hợp lệ.",
                    flush=True,
                )
            finally:
                engine.dispose()
        return

    if args.backup:
        bundle = create_coordinated_backup(SessionLocal, settings.STORAGE_DIR, settings.BACKUP_DIR)
        print(f"Đã tạo bản sao lưu đồng bộ (DB + STORAGE_DIR): {bundle}", flush=True)
        return

    if args.migrate_paths:
        report = migrate_storage_paths(
            SessionLocal,
            settings.STORAGE_DIR,
            old_root=args.old_root,
            dry_run=args.dry_run,
        )
        mode_label = "Dry-run" if report.dry_run else "Đã cập nhật"
        print(
            f"{mode_label} đường dẫn STORAGE_DIR: migrated={len(report.migrated_document_ids)}, "
            f"unchanged={len(report.unchanged_document_ids)}, expired={len(report.expired_document_ids)}, "
            f"unresolved={len(report.unresolved_document_ids)}.",
            flush=True,
        )
        if report.unresolved_document_ids:
            raise SystemExit(1)
        return

    report = validate_storage_paths(SessionLocal, settings.STORAGE_DIR)
    print(
        f"STORAGE_DIR ({report.storage_root}): writable={report.writable}, "
        f"valid_docs={len(report.valid_document_ids)}, expired_docs={len(report.expired_document_ids)}, "
        f"valid_citations={len(report.valid_citation_ids)}.",
        flush=True,
    )
    if not report.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
