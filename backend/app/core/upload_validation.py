"""BR01 validation of uploaded files, independent of browser checks."""
from fastapi import HTTPException, UploadFile

MB = 1024 * 1024
MAX_FILES = 5
MAX_FILE_BYTES = 5 * MB
MAX_BATCH_BYTES = 50 * MB
ALLOWED_EXTENSIONS = {"pdf", "docx", "pptx"}
READ_CHUNK_BYTES = 64 * 1024


def error(code: str, message: str) -> dict:
    return {"code": code, "message": message}


async def validate_uploads(files: list[UploadFile]) -> list[dict]:
    batch_errors = []
    if not files:
        batch_errors.append(error("files_required", "Select at least one file."))
    if len(files) > MAX_FILES:
        batch_errors.append(error("too_many_files", "Maximum 5 files per batch."))

    results = []
    total_bytes = 0
    for index, file in enumerate(files):
        filename = file.filename or ""
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        errors = []
        if extension not in ALLOWED_EXTENSIONS:
            errors.append(error("invalid_format", "Only PDF, DOCX and PPTX files are allowed."))
        if index >= MAX_FILES:
            errors.append(error("too_many_files", "Maximum 5 files per batch."))

        # Count actual bytes, ignoring client MIME/size claims; never read an entire file into RAM.
        size_bytes = 0
        try:
            await file.seek(0)
            while chunk := await file.read(READ_CHUNK_BYTES):
                size_bytes += len(chunk)
        finally:
            await file.seek(0)
        total_bytes += size_bytes
        if size_bytes == 0:
            errors.append(error("empty_file", "File must not be empty."))
        if size_bytes > MAX_FILE_BYTES:
            errors.append(error("file_too_large", "Each file must be at most 5 MB."))
        results.append({"index": index, "filename": filename, "size_bytes": size_bytes, "errors": errors})

    if total_bytes > MAX_BATCH_BYTES:
        total_error = error("batch_too_large", "Combined file size must be at most 50 MB.")
        batch_errors.append(total_error)
        for result in results:
            result["errors"].append(total_error)

    failed_files = [result for result in results if result["errors"]]
    if batch_errors or failed_files:
        raise HTTPException(status_code=422, detail={
            "code": "upload_validation_failed",
            "batch_errors": batch_errors,
            "files": failed_files,
        })
    return [{"filename": result["filename"], "size_bytes": result["size_bytes"]} for result in results]
