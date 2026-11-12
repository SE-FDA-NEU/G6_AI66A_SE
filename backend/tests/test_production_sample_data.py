"""Tests for M5-04 production sample data, two ordinary accounts, P0 Table/Bullet/Concept results, DOCX/PPTX reader samples, retention and idempotent rerun."""
from datetime import datetime, timedelta
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "test"))
from acceptance_fixtures import DEMO_ACCOUNTS, seed_production_demo
from app.core.config import settings
from app.core.security import create_access_token
from app.models import Citation, Document, FileFormat, Folder, Job, JobMode, JobStatus, User
from app.services.storage_ops import validate_storage_paths


def test_production_sample_seed_prepares_two_accounts_p0_formats_real_results_and_idempotent_rerun(
    client, session_factory
):
    storage_root = settings.STORAGE_DIR
    summary = seed_production_demo(session_factory, storage_root)

    primary_id = summary["primary_owner_id"]
    peer_id = summary["peer_owner_id"]
    assert primary_id != peer_id
    assert len(summary["primary_pdf_ids"]) == 20
    assert len(summary["primary_office_ids"]) == 2
    assert len(summary["primary_job_ids"]) == 3
    assert len(summary["peer_document_ids"]) == 3

    # Verify all seeded files, .reader PDFs, SHA-256 digests and citations on disk
    validation = validate_storage_paths(session_factory, storage_root)
    assert validation.ok
    assert len(validation.valid_document_ids) == 25  # 22 for Account A + 3 for Account B
    assert len(validation.valid_citation_ids) >= 15

    # Verify Account A via API: 22 documents (20 PDFs + 1 DOCX + 1 PPTX), including 5 contracts and 15-page PDF
    headers_a = {"Authorization": f"Bearer {create_access_token({'sub': str(primary_id)})}"}
    headers_b = {"Authorization": f"Bearer {create_access_token({'sub': str(peer_id)})}"}

    docs_a = client.get("/documents", params={"limit": 100}, headers=headers_a).json()
    assert len(docs_a) == 22
    by_name = {d["original_filename"]: d for d in docs_a}
    for i in range(1, 6):
        assert f"contract-{i}.pdf" in by_name
    assert by_name["report-15-pages.pdf"]["page_count"] == 15
    assert by_name["sample-policy-handbook.docx"]["file_format"] == "DOCX"
    assert by_name["sample-architecture-deck.pptx"]["file_format"] == "PPTX"

    # Verify DOCX and PPTX reader pages and rendered PDF streams work
    for office_name in ("sample-policy-handbook.docx", "sample-architecture-deck.pptx"):
        doc_id = by_name[office_name]["id"]
        pages_resp = client.get(f"/documents/{doc_id}/pages", headers=headers_a)
        assert pages_resp.status_code == 200
        pages_payload = pages_resp.json()
        assert pages_payload["reader_layout"] == "text"
        assert pages_payload["page_count"] >= 2
        pdf_resp = client.get(pages_payload["reader_url"], headers=headers_a)
        assert pdf_resp.status_code == 200
        assert pdf_resp.content.startswith(b"%PDF")

    # Verify real Table, Bullet, and Concept job results and citations for Account A
    jobs_a = client.get("/jobs", headers=headers_a).json()
    modes_a = {j["mode"]: j for j in jobs_a if j["status"] == "completed"}
    assert set(modes_a.keys()) == {"table", "bullet", "concept"}

    table_detail = client.get(f"/jobs/{modes_a['table']['id']}", headers=headers_a).json()
    assert table_detail["file_count"] == 5 and table_detail["completed_count"] == 5
    assert len(table_detail["result_data"]["documents"]) == 5
    assert len(table_detail["citations"]) >= 14  # 5 contracts * 3 fields (minus 1 unverified null term)

    bullet_detail = client.get(f"/jobs/{modes_a['bullet']['id']}", headers=headers_a).json()
    assert bullet_detail["completed_count"] == 1
    report_id = by_name["report-15-pages.pdf"]["id"]
    summary_resp = client.get(f"/documents/{report_id}/summary", headers=headers_a)
    assert summary_resp.status_code == 200
    assert summary_resp.json()["document"]["mode"] == "bullet"

    concept_detail = client.get(f"/jobs/{modes_a['concept']['id']}", headers=headers_a).json()
    assert concept_detail["completed_count"] == 1
    concept_doc = next(iter(concept_detail["result_data"]["documents"].values()))
    assert len(concept_doc["output"]["concepts"]) >= 3

    # Verify cross-document search across the >20 seeded documents (PDF + DOCX + PPTX)
    for query, expected_doc in [
        ("Orchid liquidity covenant", "report-15-pages.pdf"),
        ("Amber escrow release", "contract-24-pages.pdf"),
        ("Supplier quotations must be compared", "sample-policy-handbook.docx"),
        ("Multi-Document Comparison Table", "sample-architecture-deck.pptx"),
    ]:
        s_resp = client.get("/search", params={"q": query}, headers=headers_a)
        assert s_resp.status_code == 200
        assert any(hit["doc_name"] == expected_doc for hit in s_resp.json()["hits"])

    # Verify two-account ownership isolation (US05 / BR07)
    docs_b = client.get("/documents", params={"limit": 100}, headers=headers_b).json()
    assert len(docs_b) == 3
    assert client.get(f"/documents/{report_id}", headers=headers_b).status_code == 403
    assert client.get(f"/jobs/{modes_a['table']['id']}", headers=headers_b).status_code == 404
    assert client.get("/search", params={"q": "Amber escrow release"}, headers=headers_b).json()["hits"] == []

    # Verify rerun safety & retention renewal: human edits stay intact and near-expiry demo rows renew
    now = datetime.utcnow()
    with session_factory() as db:
        edited_doc = db.get(Document, report_id)
        edited_doc.user_label = "Human Verified 15-Page Report"
        edited_doc.folder_id = None
        edited_doc.expires_at = now + timedelta(days=5)  # < 14 days remaining
        db.commit()

    rerun = seed_production_demo(session_factory, storage_root)
    assert rerun["primary_job_ids"] == summary["primary_job_ids"]

    with session_factory() as db:
        reloaded = db.get(Document, report_id)
        assert reloaded.user_label == "Human Verified 15-Page Report"
        assert reloaded.folder_id is None
        assert reloaded.expires_at > now + timedelta(days=25)
        assert db.query(Document).filter_by(owner_id=primary_id).count() == 22
        assert db.query(Job).filter_by(owner_id=primary_id).count() == 3
