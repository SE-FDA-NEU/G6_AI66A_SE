"""Human label decisions persist independently of AI predictions and folders."""
from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from app.core.security import create_access_token
from app.models import Document, FileFormat, Folder, ReviewState
from app.services.reader_extraction import extract_document_for_reader
from test_pdf_extraction import make_pdf


def snapshot(document):
    return {column.name: deepcopy(getattr(document, column.name)) for column in Document.__table__.columns}


def label_metadata(data):
    # Successful edits now renew retention (#141); all other metadata stays fixed.
    return {key: value for key, value in data.items() if key not in ('last_accessed_at', 'expires_at')}


@pytest.fixture
def labelled_document(session_factory, tmp_path):
    source = make_pdf(tmp_path / 'label.pdf', [b'BT /F1 12 Tf 30 720 Td (Macroeconomics report.) Tj ET'])
    with session_factory() as db:
        folder = Folder(owner_id=123, name='Economics 101')
        db.add(folder); db.flush()
        document = Document(owner_id=123, folder_id=folder.id, original_filename='report.pdf',
                            storage_path=str(source), file_format=FileFormat.PDF, file_size_bytes=source.stat().st_size,
                            ai_label='Macroeconomics', ai_confidence=.99, review_state=ReviewState.NEEDS_REVIEW,
                            last_accessed_at=datetime(2026, 1, 1), expires_at=datetime.utcnow() + timedelta(days=30))
        db.add(document); db.commit()
        document_id = document.id
    extract_document_for_reader(document_id, session_factory)
    return document_id


@pytest.mark.parametrize('confidence', [.79, .8, .99, None])
def test_prediction_never_confirms_itself_and_confirm_only_snapshots_ai_label(client, session_factory, labelled_document, confidence):
    document_id = labelled_document
    with session_factory() as db:
        document = db.get(Document, document_id)
        document.ai_confidence = confidence
        db.commit()
        before = snapshot(document)
    initial = client.get('/documents').json()[0]
    assert initial['review_state'] == 'needs_review' and initial['user_label'] is None
    confirmed = client.patch(f'/documents/{document_id}/label', json={'review_state': 'confirmed'})
    assert confirmed.status_code == 200
    assert confirmed.json()['user_label'] == 'Macroeconomics' and confirmed.json()['review_state'] == 'confirmed'
    assert confirmed.json()['ai_confidence'] == confidence
    with session_factory() as db:
        assert label_metadata(snapshot(db.get(Document, document_id))) == label_metadata({**before, 'user_label': 'Macroeconomics', 'review_state': ReviewState.CONFIRMED})
    assert label_metadata(client.patch(f'/documents/{document_id}/label', json={'review_state': 'confirmed'}).json()) == label_metadata(confirmed.json())


def test_manual_edit_and_partial_review_changes_persist_on_all_document_reads(client, session_factory, labelled_document):
    document_id = labelled_document
    with session_factory() as db:
        before = snapshot(db.get(Document, document_id))
    endpoint = f'/documents/{document_id}/label'
    edited = client.patch(endpoint, json={'user_label': '  Nghiên cứu kinh tế  '})
    assert edited.status_code == 200
    assert edited.json()['user_label'] == 'Nghiên cứu kinh tế' and edited.json()['review_state'] == 'confirmed'
    draft = client.patch(endpoint, json={'review_state': 'needs_review'})
    assert draft.json()['user_label'] == 'Nghiên cứu kinh tế' and draft.json()['review_state'] == 'needs_review'
    saved_draft = client.patch(endpoint, json={'user_label': 'Edited draft', 'review_state': 'needs_review'})
    assert saved_draft.json()['user_label'] == 'Edited draft' and saved_draft.json()['review_state'] == 'needs_review'
    confirmed = client.patch(endpoint, json={'review_state': 'confirmed'})
    assert confirmed.json()['user_label'] == 'Edited draft'  # Existing human choice wins over the AI suggestion.
    with session_factory() as db:
        assert label_metadata(snapshot(db.get(Document, document_id))) == label_metadata({**before, 'user_label': 'Edited draft', 'review_state': ReviewState.CONFIRMED})
    for response in [client.get(f'/documents/{document_id}'), client.get('/documents'), client.get(f'/documents/{document_id}/pages')]:
        assert response.status_code == 200
        data = response.json()[0] if isinstance(response.json(), list) else response.json()
        assert data['user_label'] == 'Edited draft' and data['review_state'] == 'confirmed'
        assert data['ai_label'] == 'Macroeconomics' and data['ai_confidence'] == .99
        assert data['folder_id'] == before['folder_id']
    assert len(client.get('/documents?label=Macroeconomics').json()) == 1
    assert client.get('/documents?label=Edited%20draft').json() == []


@pytest.mark.parametrize('payload', [{'user_label': None}, {'user_label': None, 'review_state': 'needs_review'}])
def test_clearing_human_decision_restores_needs_review_without_changing_ai_or_folder(client, session_factory, labelled_document, payload):
    document_id = labelled_document
    endpoint = f'/documents/{document_id}/label'
    assert client.patch(endpoint, json={'user_label': 'Custom label'}).status_code == 200
    with session_factory() as db:
        before = snapshot(db.get(Document, document_id))
    response = client.patch(endpoint, json=payload)
    assert response.status_code == 200 and response.json()['user_label'] is None
    assert response.json()['review_state'] == 'needs_review'
    with session_factory() as db:
        assert label_metadata(snapshot(db.get(Document, document_id))) == label_metadata({**before, 'user_label': None, 'review_state': ReviewState.NEEDS_REVIEW})


def test_no_ai_suggestion_requires_an_explicit_human_label_before_confirmation(client, session_factory, labelled_document):
    with session_factory() as db:
        document = db.get(Document, labelled_document)
        document.ai_label = None; document.ai_confidence = None
        db.commit()
    endpoint = f'/documents/{labelled_document}/label'
    assert client.patch(endpoint, json={'review_state': 'confirmed'}).status_code == 422
    response = client.patch(endpoint, json={'user_label': 'My classification'})
    assert response.status_code == 200 and response.json()['review_state'] == 'confirmed'
    assert response.json()['ai_label'] is None and response.json()['ai_confidence'] is None


def test_label_accepts_the_storage_length_boundary(client, labelled_document):
    response = client.patch(f'/documents/{labelled_document}/label', json={'user_label': 'a' * 100})
    assert response.status_code == 200 and response.json()['user_label'] == 'a' * 100


@pytest.mark.parametrize('payload', [
    {}, {'user_label': ''}, {'user_label': ' \t\n'}, {'user_label': 'x' * 101}, {'user_label': True},
    {'user_label': 123}, {'user_label': 1.5}, {'user_label': []}, {'user_label': {}},
    {'review_state': None}, {'review_state': 'high_confidence'}, {'review_state': 'CONFIRMED'},
    {'review_state': ''}, {'review_state': True}, {'user_label': None, 'review_state': 'confirmed'},
    {'user_label': 'Allowed', 'ai_label': 'Tampered'}, {'user_label': 'Allowed', 'ai_confidence': 1.},
    {'user_label': 'Allowed', 'folder_id': None}, {'user_label': 'Allowed', 'owner_id': 124},
])
def test_invalid_edits_leave_the_entire_document_unchanged(client, session_factory, labelled_document, payload):
    with session_factory() as db:
        before = snapshot(db.get(Document, labelled_document))
    assert client.patch(f'/documents/{labelled_document}/label', json=payload).status_code == 422
    with session_factory() as db:
        assert snapshot(db.get(Document, labelled_document)) == before


def test_other_owner_and_missing_document_both_return_404_without_mutation(client, session_factory, labelled_document):
    peer = {'Authorization': f"Bearer {create_access_token({'sub': '124'})}"}
    with session_factory() as db:
        before = snapshot(db.get(Document, labelled_document))
    denied = client.patch(f'/documents/{labelled_document}/label', headers=peer, json={'user_label': 'Intrusion'})
    missing = client.patch('/documents/99999/label', json={'user_label': 'Missing'})
    assert denied.status_code == missing.status_code == 404
    assert denied.json() == missing.json() == {'detail': 'Document not found'}
    assert client.patch(f'/documents/{labelled_document}/label', headers={'Authorization': 'Bearer invalid'},
                        json={'review_state': 'confirmed'}).status_code == 401
    with session_factory() as db:
        assert snapshot(db.get(Document, labelled_document)) == before
