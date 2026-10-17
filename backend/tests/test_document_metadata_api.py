"""Tests for Document Metadata API exposure and folder placement preservation (US10).

Verifies:
- GET /documents/{id}/pages returns ai_label, ai_confidence, review_state, folder_id, user_label.
- Folder placement remains unchanged and is never overwritten or auto-assigned by metadata extraction.
- Ownership protection from US05 applies.
"""
from datetime import datetime, timedelta
import pytest
from app.core.security import create_access_token
from app.models import Document, FileFormat, Folder, ReviewState
from app.services.reader_extraction import extract_document_for_reader
from test_pdf_extraction import make_pdf


@pytest.fixture
def sample_pdf(tmp_path):
    return make_pdf(tmp_path / 'metadata_test.pdf', [
        b'BT /F1 12 Tf 72 720 Td (Page 1 sample content) Tj ET',
    ])


def create_doc_with_metadata(session_factory, owner_id, pdf_path, ai_label, ai_confidence, review_state, folder_id=None, user_label=None):
    with session_factory() as db:
        doc = Document(
            owner_id=owner_id,
            original_filename='metadata_doc.pdf',
            storage_path=str(pdf_path),
            file_format=FileFormat.PDF,
            file_size_bytes=pdf_path.stat().st_size,
            page_count=1,
            ai_label=ai_label,
            ai_confidence=ai_confidence,
            review_state=review_state,
            folder_id=folder_id,
            user_label=user_label,
            last_accessed_at=datetime(2026, 1, 1),
            expires_at=datetime(2026, 1, 1) + timedelta(days=30),
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id = doc.id

    extract_document_for_reader(doc_id, session_factory)
    return doc_id


def test_reader_pages_exposes_metadata_and_preserves_folder_id(client, session_factory, sample_pdf):
    # 1. Document with unassigned folder (folder_id=None)
    doc_id_unassigned = create_doc_with_metadata(
        session_factory,
        owner_id=123,
        pdf_path=sample_pdf,
        ai_label='Hợp đồng',
        ai_confidence=0.87,
        review_state=ReviewState.NEEDS_REVIEW,
        folder_id=None,
        user_label=None,
    )

    res = client.get(f'/documents/{doc_id_unassigned}/pages')
    assert res.status_code == 200
    data = res.json()
    assert data['ai_label'] == 'Hợp đồng'
    assert data['ai_confidence'] == 0.87
    assert data['review_state'] == 'needs_review'
    assert data['folder_id'] is None
    assert data['user_label'] is None
    assert data['original_filename'] == 'metadata_doc.pdf'

    # 2. Document with existing folder
    with session_factory() as db:
        test_folder = Folder(owner_id=123, name='Tài liệu kinh doanh')
        db.add(test_folder)
        db.commit()
        db.refresh(test_folder)
        test_folder_id = test_folder.id

    doc_id_assigned = create_doc_with_metadata(
        session_factory,
        owner_id=123,
        pdf_path=sample_pdf,
        ai_label='Báo cáo',
        ai_confidence=0.72,
        review_state=ReviewState.NEEDS_REVIEW,
        folder_id=test_folder_id,
        user_label='Tài liệu nội bộ',
    )

    res2 = client.get(f'/documents/{doc_id_assigned}/pages')
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2['ai_label'] == 'Báo cáo'
    assert data2['ai_confidence'] == 0.72
    assert data2['review_state'] == 'needs_review'
    assert data2['folder_id'] == test_folder_id
    assert data2['user_label'] == 'Tài liệu nội bộ'

    # 3. Verify GET /documents (used by workspace document rows) returns the exact metadata and unchanged folder placement
    res_list = client.get('/documents')
    assert res_list.status_code == 200
    docs_list = res_list.json()
    assert len(docs_list) >= 2
    by_id = {d['id']: d for d in docs_list}

    # Verify doc with null folder placement remained null (never auto-assigned)
    assert by_id[doc_id_unassigned]['folder_id'] is None
    assert by_id[doc_id_unassigned]['ai_label'] == 'Hợp đồng'
    assert by_id[doc_id_unassigned]['ai_confidence'] == 0.87
    assert by_id[doc_id_unassigned]['review_state'] == 'needs_review'

    # Verify doc with assigned folder placement remained untouched
    assert by_id[doc_id_assigned]['folder_id'] == test_folder_id
    assert by_id[doc_id_assigned]['ai_label'] == 'Báo cáo'
    assert by_id[doc_id_assigned]['ai_confidence'] == 0.72
    assert by_id[doc_id_assigned]['user_label'] == 'Tài liệu nội bộ'


@pytest.mark.parametrize("confidence,expected_state", [
    (0.87, 'needs_review'),
    (0.80, 'needs_review'),
    (0.79, 'needs_review'),
    (0.72, 'needs_review'),
])
def test_confidence_threshold_values_persisted(client, session_factory, sample_pdf, confidence, expected_state):
    doc_id = create_doc_with_metadata(
        session_factory,
        owner_id=123,
        pdf_path=sample_pdf,
        ai_label='Thử nghiệm',
        ai_confidence=confidence,
        review_state=ReviewState.NEEDS_REVIEW,
        folder_id=None,
    )
    res = client.get(f'/documents/{doc_id}/pages')
    assert res.status_code == 200
    data = res.json()
    assert data['ai_confidence'] == confidence
    assert data['folder_id'] is None



def test_reader_pages_cross_account_protection(client, session_factory, sample_pdf):
    # Document owned by user 123
    doc_id = create_doc_with_metadata(
        session_factory,
        owner_id=123,
        pdf_path=sample_pdf,
        ai_label='Bảo mật',
        ai_confidence=0.95,
        review_state=ReviewState.CONFIRMED,
        folder_id=None,
    )

    # User 124 (different user) tries to access
    other_token = f"Bearer {create_access_token({'sub': '124'})}"
    res = client.get(f'/documents/{doc_id}/pages', headers={'Authorization': other_token})
    assert res.status_code == 403
    assert res.json()['detail'] == 'Access denied'


def test_get_page_text_endpoint_authorized_access(client, session_factory, sample_pdf):
    doc_id = create_doc_with_metadata(
        session_factory,
        owner_id=123,
        pdf_path=sample_pdf,
        ai_label='Lạm phát',
        ai_confidence=0.85,
        review_state=ReviewState.NEEDS_REVIEW,
    )

    # 1. Authorized owner gets page text
    res = client.get(f'/documents/{doc_id}/pages/1/text')
    assert res.status_code == 200
    data = res.json()
    assert data['document_id'] == doc_id
    assert data['page'] == 1
    assert 'Page 1 sample content' in data['text']
    assert isinstance(data['positions'], list)

    # 2. Non-existent page returns 404
    res_404 = client.get(f'/documents/{doc_id}/pages/99/text')
    assert res_404.status_code == 404
    assert res_404.json()['detail'] == 'Page not found'

    # 3. Cross-account request returns 403
    other_token = f"Bearer {create_access_token({'sub': '124'})}"
    res_403 = client.get(f'/documents/{doc_id}/pages/1/text', headers={'Authorization': other_token})
    assert res_403.status_code == 403
    assert res_403.json()['detail'] == 'Access denied'


