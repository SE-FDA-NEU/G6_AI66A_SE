"""Persist a validated upload batch atomically with its database records."""
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from app.models import Document, FileFormat, Job, JobFile, JobStatus, User
from app.core.upload_validation import READ_CHUNK_BYTES


def save_upload_job(db, user_id, files, validated, mode, storage_root, language="vi"):
    if db.get(User, user_id) is None:
        raise HTTPException(401, "Account no longer exists.")
    batch_dir = Path(storage_root).resolve() / str(user_id) / uuid4().hex
    created_directory = False
    try:
        batch_dir.mkdir(parents=True)
        created_directory = True
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        job = Job(owner_id=user_id, mode=mode, status=JobStatus.PENDING,
                  file_count=len(files), completed_count=0,
                  result_data={"schema_version": 1, "language": language, "documents": {}})
        db.add(job)
        db.flush()
        for upload, metadata in zip(files, validated):
            # Client filenames are metadata, never used as storage paths.
            filename = metadata['filename'].replace('\\', '/').rsplit('/', 1)[-1]
            if not filename or len(filename) > 255:
                raise HTTPException(422, "Filename must be between 1 and 255 characters.")
            extension = filename.rsplit('.', 1)[-1].lower()
            path = batch_dir / f"{uuid4().hex}.{extension}"
            upload.file.seek(0)
            with path.open('xb') as target:
                shutil.copyfileobj(upload.file, target, length=READ_CHUNK_BYTES)
            document = Document(
                owner_id=user_id, original_filename=filename, storage_path=str(path),
                file_format=FileFormat(extension.upper()), file_size_bytes=metadata['size_bytes'],
                last_accessed_at=now, expires_at=now + timedelta(days=30),
            )
            db.add(document)
            db.flush()
            db.add(JobFile(job_id=job.id, document_id=document.id, status=JobStatus.PENDING))
        job_id = job.id
        db.commit()
        return job_id
    except BaseException:
        try:
            db.rollback()
        finally:
            # Remove only a directory created by this request.
            if created_directory:
                shutil.rmtree(batch_dir, ignore_errors=True)
        raise
