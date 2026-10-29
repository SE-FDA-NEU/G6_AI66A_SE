"""Tests for Document Metadata API exposure and folder placement preservation (US10).

Verifies:
- GET /documents/{id}/pages returns ai_label, ai_confidence, review_state, folder_id, user_label.
- Folder placement remains unchanged and is never overwritten or auto-assigned by metadata extraction.
- Ownership protection from US05 applies.
"""
from datetime import datetime, timedelta
import pytest
from app.core.security import create_access_token
from app.models import Document, FileFormat, Folder, Job, ReviewState
from app.services.processing import process_job
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


@pytest.mark.parametrize('confidence,confidence_level', [
    pytest.param(0.79, 'low', id='TC-US04-01-below-80'),
    pytest.param(0.80, 'high', id='TC-US04-02-at-80'),
    pytest.param(0.81, 'high', id='TC-US04-03-above-80'),
])
@pytest.mark.parametrize('review_state', list(ReviewState), ids=lambda state: state.value)
@pytest.mark.parametrize('assigned_folder', [False, True], ids=['unassigned', 'assigned'])
def test_confidence_threshold_values_persisted(
        client, session_factory, sample_pdf, confidence, confidence_level, review_state, assigned_folder):
    uploaded = client.post('/upload', data={'mode': 'table'}, files=[
        ('files', ('metadata_doc.pdf', sample_pdf.read_bytes(), 'application/pdf')),
    ])
    assert uploaded.status_code == 202
    job_id = int(uploaded.json()['jobId'])
    with session_factory() as db:
        document = db.get(Job, job_id).job_files[0].document
        doc_id = document.id
        folder_id = None
        if assigned_folder:
            folder = Folder(owner_id=123, name='Original folder')
            db.add(folder)
            db.flush()
            folder_id = folder.id
        document.folder_id = folder_id
        document.review_state = review_state
        document.user_label = 'Human label' if review_state == ReviewState.CONFIRMED else None
        user_label = document.user_label
        db.commit()

    async def analyzer(document, mode):
        return {'output': {'type': 'table'},
                'label': {'ai_label': 'Fixed AI label', 'ai_confidence': confidence}}

    process_job(job_id, session_factory, analyzer=analyzer)
    response = client.get(f'/jobs/{job_id}')
    assert response.status_code == 200
    saved = response.json()
    assert saved['status'] == 'completed'
    result = saved['result_data']['documents'][str(doc_id)]
    assert result['document_id'] == doc_id
    assert result['original_filename'] == 'metadata_doc.pdf'
    assert result['label'] == {
        'ai_label': 'Fixed AI label', 'ai_confidence': confidence,
        'confidence_level': confidence_level, 'review_state': review_state.value,
        'user_label': user_label,
    }
    pages = client.get(f'/documents/{doc_id}/pages')
    listing = client.get('/documents')
    assert pages.status_code == listing.status_code == 200
    listed = next(item for item in listing.json() if item['id'] == doc_id)
    for metadata in (pages.json(), listed):
        assert metadata['ai_label'] == 'Fixed AI label'
        assert metadata['ai_confidence'] == confidence
        assert metadata['review_state'] == review_state.value
        assert metadata['user_label'] == user_label
        assert metadata['folder_id'] == folder_id
    with session_factory() as db:
        document = db.get(Document, doc_id)
        assert document.folder_id == folder_id
        assert document.review_state == review_state
        assert document.user_label == user_label


@pytest.mark.parametrize('label', [
    pytest.param({'ai_label': '', 'ai_confidence': 0.8}, id='TC-US04-04-empty-label'),
    pytest.param({'ai_label': 'x' * 101, 'ai_confidence': 0.8}, id='TC-US04-05-long-label'),
    pytest.param({'ai_label': 'Fixed AI label'}, id='TC-US04-06-missing-confidence'),
    pytest.param({'ai_confidence': 0.8}, id='TC-US04-07-missing-label'),
    pytest.param({'ai_label': 'Fixed AI label', 'ai_confidence': -0.01}, id='TC-US04-08-negative-confidence'),
    pytest.param({'ai_label': 'Fixed AI label', 'ai_confidence': 1.01}, id='TC-US04-09-confidence-over-100'),
])
def test_invalid_mocked_label_is_not_published(client, session_factory, sample_pdf, label):
    uploaded = client.post('/upload', data={'mode': 'table'}, files=[
        ('files', ('metadata_doc.pdf', sample_pdf.read_bytes(), 'application/pdf')),
    ])
    assert uploaded.status_code == 202
    job_id = int(uploaded.json()['jobId'])
    with session_factory() as db:
        document = db.get(Job, job_id).job_files[0].document
        doc_id = document.id
        folder = Folder(owner_id=123, name='Keep this folder')
        db.add(folder)
        db.flush()
        folder_id = folder.id
        document.folder_id = folder_id
        document.ai_label = 'Previous AI label'
        document.ai_confidence = 0.9
        document.review_state = ReviewState.CONFIRMED
        document.user_label = 'Human label'
        db.commit()

    async def analyzer(document, mode):
        return {'output': {'type': 'table'}, 'label': label}

    process_job(job_id, session_factory, analyzer=analyzer)
    response = client.get(f'/jobs/{job_id}')
    assert response.status_code == 200
    saved = response.json()
    assert saved['status'] == saved['job_files'][0]['status'] == 'failed'
    assert 'invalid_result' in saved['job_files'][0]['error_message']
    assert str(doc_id) not in saved['result_data']['documents']
    assert saved['citations'] == []
    listing = client.get('/documents')
    assert listing.status_code == 200
    metadata = next(item for item in listing.json() if item['id'] == doc_id)
    assert metadata['ai_label'] == 'Previous AI label'
    assert metadata['ai_confidence'] == 0.9
    assert metadata['folder_id'] == folder_id
    assert metadata['review_state'] == 'confirmed'
    assert metadata['user_label'] == 'Human label'



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


