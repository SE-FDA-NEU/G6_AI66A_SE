"""TC-US06 upload boundaries use binary MB (1024 * 1024 bytes).

Five valid files reach at most 25 MB, so the defensive 50 MB guard is
exercised separately with oversized files; it is not a valid-batch scenario.
"""
import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from app.core.upload_validation import MB, validate_uploads
from app.models import Document, Job, JobFile
from app.core.config import settings


@pytest.fixture
def no_upload_artifacts(client, session_factory, job_queue):
    yield
    with session_factory() as db:
        for model in (Job, JobFile, Document):
            assert db.query(model).count() == 0
    assert job_queue.enqueued == []
    assert not any(path.is_file() for path in settings.STORAGE_DIR.rglob('*'))


def part(name="report.pdf", size=16, content_type="application/octet-stream"):
    return ("files", (name, b"x" * size, content_type))


def detail(response):
    assert response.status_code == 422
    result = response.json()["detail"]
    assert result["code"] == "upload_validation_failed"
    return result


@pytest.mark.parametrize("name", ["report.PDF", "notes.docx", "slides.PpTx"])
def test_valid_extensions_with_generic_mime(client, session_factory, name):
    """TC-US06-01: supported formats are accepted regardless of MIME claims."""
    response = client.post("/upload", files=[part(name)])
    assert response.status_code == 202
    assert response.json()['jobId'].isdigit()
    with session_factory() as db:
        document = db.query(Document).one()
        assert document.original_filename == name
        assert document.file_size_bytes == 16


def test_five_files_at_exact_size_boundary(client, session_factory):
    """TC-US06-02: five maximum-size files total 25 MB, below the batch cap."""
    response = client.post("/upload", files=[part(f"contract-{i}.pdf", 5 * MB) for i in range(5)])
    assert response.status_code == 202
    with session_factory() as db:
        documents = db.query(Document).all()
        assert len(documents) == 5
        assert sum(document.file_size_bytes for document in documents) == 25 * MB


@pytest.mark.parametrize("name", ["malware.exe", "report.pdf.exe", "README", "notes.txt"])
@pytest.mark.usefixtures("no_upload_artifacts")
def test_disallowed_extensions_even_when_mime_claims_pdf(client, name):
    """TC-US06-03: unsupported suffixes cannot bypass validation with PDF MIME."""
    result = detail(client.post("/upload", files=[part(name, content_type="application/pdf")]))
    assert result["files"][0]["filename"] == name
    assert result["files"][0]["errors"][0]["code"] == "invalid_format"


@pytest.mark.usefixtures("no_upload_artifacts")
def test_one_byte_above_file_limit(client):
    """TC-US06-04: 5 MB + 1 byte is rejected without side effects."""
    result = detail(client.post("/upload", files=[part(size=5 * MB + 1)]))
    assert result["files"][0]["size_bytes"] == 5 * MB + 1
    assert result["files"][0]["errors"][0]["code"] == "file_too_large"


@pytest.mark.usefixtures("no_upload_artifacts")
def test_sixth_file_has_its_own_error(client):
    """TC-US06-05: six files reject the whole batch, including valid predecessors."""
    result = detail(client.post("/upload", files=[part(f"{i}.pdf") for i in range(6)]))
    assert result["batch_errors"][0]["code"] == "too_many_files"
    assert [file["index"] for file in result["files"]] == [5]
    assert result["files"][0]["filename"] == "5.pdf"


@pytest.mark.parametrize("size,exceeds", [(50 * MB, False), (50 * MB + 1, True)])
@pytest.mark.usefixtures("no_upload_artifacts")
def test_combined_size_boundary_is_checked_independently(client, size, exceeds):
    """TC-US06-06: isolated defensive 50 MB guard using invalid oversized files."""
    # Valid batches can only reach 25 MB. Oversized files still exercise the 50 MB guard.
    result = detail(client.post("/upload", files=[
        part("large-a.pdf", size // 2), part("large-b.pdf", size - size // 2),
    ]))
    codes = [error["code"] for error in result["batch_errors"]]
    assert ("batch_too_large" in codes) is exceeds
    assert "file_too_large" in [error["code"] for error in result["files"][0]["errors"]]
    assert sum(file["size_bytes"] for file in result["files"]) == size
    for file in result["files"]:
        assert ("batch_too_large" in [error["code"] for error in file["errors"]]) is exceeds


@pytest.mark.usefixtures("no_upload_artifacts")
def test_reports_all_failures_and_identifies_duplicate_filenames_by_index(client):
    result = detail(client.post("/upload", files=[
        part("valid.pdf"), part("bad.exe"), part("same.docx", 5 * MB + 1), part("same.docx"),
    ]))
    assert [(file["index"], file["filename"]) for file in result["files"]] == [(1, "bad.exe"), (2, "same.docx")]
    assert result["batch_errors"] == []


@pytest.mark.usefixtures("no_upload_artifacts")
def test_single_file_can_report_multiple_reasons(client):
    result = detail(client.post("/upload", files=[part("bad.exe", 5 * MB + 1)]))
    assert {error["code"] for error in result["files"][0]["errors"]} == {"invalid_format", "file_too_large"}


@pytest.mark.usefixtures("no_upload_artifacts")
def test_missing_files_has_structured_error(client):
    result = detail(client.post("/upload"))
    assert result["batch_errors"][0]["code"] == "files_required"
    assert result["files"] == []


def test_swagger_files_schema_is_binary_array(client):
    schema = client.get('/openapi.json').json()
    body = schema['paths']['/upload']['post']['requestBody']['content']['multipart/form-data']['schema']
    fields = schema['components']['schemas'][body['$ref'].rsplit('/', 1)[-1]]['properties']
    assert fields['files']['type'] == 'array'
    assert fields['files']['items'] == {'type': 'string', 'format': 'binary'}
    assert 'anyOf' not in fields['files']


@pytest.mark.parametrize("authorization", [None, "Bearer forged-token"])
@pytest.mark.usefixtures("no_upload_artifacts")
def test_unauthenticated_upload_rejected(client, authorization):
    client.headers.pop("Authorization")
    headers = {"Authorization": authorization} if authorization else {}
    assert client.post("/upload", headers=headers, files=[part()]).status_code == 401


def test_cookie_session_is_supported(client):
    token = client.headers.pop("Authorization").split(" ", 1)[1]
    client.cookies.set("documind_session", token)
    assert client.post("/upload", files=[part()]).status_code == 202


@pytest.mark.parametrize("actual_size", [16, 5 * MB + 1])
def test_reads_actual_bytes_and_rewinds_even_after_rejection(actual_size):
    upload = UploadFile(filename="report.pdf", file=BytesIO(b"x" * actual_size), size=1)
    try:
        if actual_size > 5 * MB:
            with pytest.raises(HTTPException) as caught:
                asyncio.run(validate_uploads([upload]))
            assert caught.value.status_code == 422
            assert caught.value.detail["files"][0]["size_bytes"] == actual_size
        else:
            assert asyncio.run(validate_uploads([upload])) == [
                {"filename": "report.pdf", "size_bytes": actual_size},
            ]
        assert upload.file.tell() == 0
    finally:
        upload.file.close()


@pytest.mark.parametrize("count", [4, 5])
def test_valid_file_count_boundaries(client, session_factory, job_queue, count):
    """TC-US06-07: both four and five files create exactly one queued job."""
    response = client.post('/upload', files=[part(f'{i}.pdf') for i in range(count)])
    assert response.status_code == 202
    job_id = int(response.json()['jobId'])
    assert job_queue.enqueued == [job_id]
    with session_factory() as db:
        assert db.query(Job).one().id == job_id
        assert db.query(JobFile).count() == count
        documents = db.query(Document).all()
        assert len(documents) == count
        for document in documents:
            assert Path(document.storage_path).read_bytes() == b'x' * 16


@pytest.mark.parametrize("size", [5 * MB - 1, 5 * MB])
def test_inclusive_file_size_boundary(client, session_factory, size):
    """TC-US06-08: one byte below and exactly 5 MB are accepted and stored intact."""
    response = client.post('/upload', files=[part(size=size)])
    assert response.status_code == 202
    with session_factory() as db:
        document = db.query(Document).one()
        assert document.file_size_bytes == size
        assert Path(document.storage_path).stat().st_size == size


@pytest.mark.usefixtures('no_upload_artifacts')
def test_empty_file_rejects_entire_mixed_batch(client):
    """TC-US06-09: a named zero-byte file rejects even an otherwise valid batch."""
    result = detail(client.post('/upload', files=[part('keep.pdf'), part('empty.pdf', 0)]))
    assert result['batch_errors'] == []
    assert len(result['files']) == 1
    failure = result['files'][0]
    assert (failure['index'], failure['filename'], failure['size_bytes']) == (1, 'empty.pdf', 0)
    assert [error['code'] for error in failure['errors']] == ['empty_file']
