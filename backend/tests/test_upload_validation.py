import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token
from app.core.upload_validation import MB, validate_uploads


@pytest.fixture
def client():
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {create_access_token({'sub': '123'})}"
        yield client


def part(name="report.pdf", size=16, content_type="application/octet-stream"):
    return ("files", (name, b"x" * size, content_type))


def detail(response):
    assert response.status_code == 422
    result = response.json()["detail"]
    assert result["code"] == "upload_validation_failed"
    return result


@pytest.mark.parametrize("name", ["report.PDF", "notes.docx", "slides.PpTx"])
def test_valid_extensions_with_generic_mime(client, name):
    response = client.post("/upload", files=[part(name)])
    assert response.status_code == 200
    assert response.json() == {
        "message": "Files validated", "user_id_from_token": 123,
        "files": [{"filename": name, "size_bytes": 16}],
    }


def test_five_files_at_exact_size_boundary(client):
    response = client.post("/upload", files=[part(f"contract-{i}.pdf", 5 * MB) for i in range(5)])
    assert response.status_code == 200
    assert len(response.json()["files"]) == 5
    assert sum(file["size_bytes"] for file in response.json()["files"]) == 25 * MB


@pytest.mark.parametrize("name", ["malware.exe", "report.pdf.exe", "README", "notes.txt"])
def test_disallowed_extensions_even_when_mime_claims_pdf(client, name):
    result = detail(client.post("/upload", files=[part(name, content_type="application/pdf")]))
    assert result["files"][0]["filename"] == name
    assert result["files"][0]["errors"][0]["code"] == "invalid_format"


def test_one_byte_above_file_limit(client):
    result = detail(client.post("/upload", files=[part(size=5 * MB + 1)]))
    assert result["files"][0]["size_bytes"] == 5 * MB + 1
    assert result["files"][0]["errors"][0]["code"] == "file_too_large"


def test_sixth_file_has_its_own_error(client):
    result = detail(client.post("/upload", files=[part(f"{i}.pdf") for i in range(6)]))
    assert result["batch_errors"][0]["code"] == "too_many_files"
    assert [file["index"] for file in result["files"]] == [5]
    assert result["files"][0]["filename"] == "5.pdf"


@pytest.mark.parametrize("size,exceeds", [(50 * MB, False), (50 * MB + 1, True)])
def test_combined_size_boundary_is_checked_independently(client, size, exceeds):
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


def test_reports_all_failures_and_identifies_duplicate_filenames_by_index(client):
    result = detail(client.post("/upload", files=[
        part("valid.pdf"), part("bad.exe"), part("same.docx", 5 * MB + 1), part("same.docx"),
    ]))
    assert [(file["index"], file["filename"]) for file in result["files"]] == [(1, "bad.exe"), (2, "same.docx")]
    assert result["batch_errors"] == []


def test_single_file_can_report_multiple_reasons(client):
    result = detail(client.post("/upload", files=[part("bad.exe", 5 * MB + 1)]))
    assert {error["code"] for error in result["files"][0]["errors"]} == {"invalid_format", "file_too_large"}


def test_missing_files_has_structured_error(client):
    result = detail(client.post("/upload"))
    assert result["batch_errors"][0]["code"] == "files_required"
    assert result["files"] == []


@pytest.mark.parametrize("authorization", [None, "Bearer forged-token"])
def test_unauthenticated_upload_rejected(client, authorization):
    client.headers.pop("Authorization")
    headers = {"Authorization": authorization} if authorization else {}
    assert client.post("/upload", headers=headers, files=[part()]).status_code == 401


def test_cookie_session_is_supported(client):
    token = client.headers.pop("Authorization").split(" ", 1)[1]
    client.cookies.set("documind_session", token)
    assert client.post("/upload", files=[part()]).status_code == 200


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
