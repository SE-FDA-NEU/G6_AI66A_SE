"""AI-label filters are exact, owner scoped and applied before pagination."""
from datetime import datetime, timedelta

import pytest

from app.core.security import create_access_token
from app.models import Document, FileFormat, Folder, ReviewState


@pytest.fixture
def labelled_documents(session_factory):
    with session_factory() as db:
        first, second, peer = [Folder(owner_id=owner, name=name) for owner, name in
                               [(123, 'Economics 101'), (123, 'Research'), (124, 'Private')]]
        db.add_all([first, second, peer]); db.flush()
        folder_ids = [first.id, second.id, None]
        labels = ['Macroeconomics'] * 8 + ['Microeconomics'] * 8 + ['Macroeconomics notes', 'macroeconomics', 'Vĩ mô', None]
        documents = []
        for number, label in enumerate(labels):
            document = Document(owner_id=123, original_filename=f'report-{number}.pdf', storage_path=f'/unused/{number}.pdf',
                                file_format=FileFormat.PDF, file_size_bytes=128, folder_id=folder_ids[number % 3],
                                ai_label=label, ai_confidence=.91, user_label='Macroeconomics' if number >= 8 else 'Reviewed differently',
                                review_state=ReviewState.CONFIRMED if number % 2 else ReviewState.NEEDS_REVIEW,
                                created_at=datetime(2026, 1, 1) + timedelta(seconds=number),
                                expires_at=datetime.utcnow() + timedelta(days=30))
            db.add(document); documents.append(document)
        db.add(Document(owner_id=124, folder_id=peer.id, original_filename='secret.pdf', storage_path='/private.pdf',
                        file_format=FileFormat.PDF, file_size_bytes=128, ai_label='Macroeconomics',
                        expires_at=datetime.utcnow() + timedelta(days=30)))
        db.commit()
        return [doc.id for doc in documents], [first.id, second.id, peer.id]


def test_eight_of_twenty_across_folders_and_clearing_restores_every_document(client, labelled_documents):
    ids, folders = labelled_documents
    unfiltered = client.get('/documents', params={'limit': 100}).json()
    assert len(unfiltered) == 20 and {doc['id'] for doc in unfiltered} == set(ids)
    assert not any(doc['ai_label'] == 'Macroeconomics' for doc in unfiltered[:10])
    filtered = client.get('/documents', params={'label': 'Macroeconomics', 'limit': 100}).json()
    assert len(filtered) == 8 and {doc['id'] for doc in filtered} == set(ids[:8])
    assert {doc['folder_id'] for doc in filtered} == {folders[0], folders[1], None}
    pages = [client.get('/documents', params={'ai_label': 'Macroeconomics', 'limit': 3, 'skip': skip}).json()
             for skip in [0, 3, 6]]
    assert [len(page) for page in pages] == [3, 3, 2]
    assert [doc['id'] for page in pages for doc in page] == [doc['id'] for doc in filtered]
    assert client.get('/documents', params={'label': 'Macroeconomics', 'skip': 8}).json() == []
    assert client.get('/documents', params={'limit': 100}).json() == unfiltered


def test_user_label_edits_never_change_ai_label_filter_meaning(client, session_factory, labelled_documents):
    ids, _ = labelled_documents
    with session_factory() as db:
        for document in db.query(Document).filter(Document.owner_id == 123):
            document.user_label = 'Unrelated correction' if document.id in ids[:8] else 'Macroeconomics'
            document.review_state = ReviewState.CONFIRMED
        db.commit()
    result = client.get('/documents?label=Macroeconomics&limit=100').json()
    assert len(result) == 8 and {doc['id'] for doc in result} == set(ids[:8])
    assert all(doc['user_label'] == 'Unrelated correction' and doc['ai_confidence'] == .91 for doc in result)


def test_combined_filters_use_and_and_clearing_only_label_keeps_folder(client, labelled_documents):
    ids, folders = labelled_documents
    params = {'label': 'Macroeconomics', 'folder_id': folders[0], 'limit': 100}
    result = client.get('/documents', params=params).json()
    assert {doc['id'] for doc in result} == {ids[0], ids[3], ids[6]}
    assert [doc['id'] for doc in client.get('/documents', params={**params, 'review_state': 'confirmed'}).json()] == [ids[3]]
    assert [doc['id'] for doc in client.get('/documents', params={**params, 'search': 'report-3'}).json()] == [ids[3]]
    assert client.get('/documents', params={**params, 'search': 'Microeconomics'}).json() == []
    restored_folder = client.get('/documents', params={'folder_id': folders[0], 'limit': 100}).json()
    assert len(restored_folder) == 7 and all(doc['folder_id'] == folders[0] for doc in restored_folder)


@pytest.mark.parametrize('label,count', [('Macro', 0), ('Macroeconomics%', 0), ('%', 0), ('MACROECONOMICS', 0),
                                         ('macroeconomics', 1), ('Vĩ mô', 1), ('Vi mo', 0), ('Unknown', 0),
                                         (' Macroeconomics', 0), ('Macroeconomics ', 0)])
def test_exact_label_never_matches_substrings_wildcards_case_or_accent_variants(client, labelled_documents, label, count):
    result = client.get('/documents', params={'label': label, 'limit': 100})
    assert result.status_code == 200 and len(result.json()) == count


def test_aliases_and_cross_account_isolation(client, labelled_documents):
    ids, folders = labelled_documents
    assert len(client.get('/documents?label=Macroeconomics&ai_label=Macroeconomics').json()) == 8
    assert len(client.get('/documents?ai_label=Macroeconomics&owner_id=124').json()) == 8
    assert client.get('/documents', params={'label': 'Macroeconomics', 'folder_id': folders[2]}).json() == []
    peer = {'Authorization': f"Bearer {create_access_token({'sub': '124'})}"}
    result = client.get('/documents?label=Macroeconomics', headers=peer).json()
    assert len(result) == 1 and result[0]['id'] not in ids
    assert client.get('/documents?label=Macroeconomics', headers={'Authorization': 'Bearer invalid'}).status_code == 401


@pytest.mark.parametrize('params', [{'label': ''}, {'ai_label': ''}, {'label': '   '}, {'ai_label': '\t'},
                                  {'label': 'x' * 101}, {'ai_label': 'x' * 101},
                                  {'label': 'Macroeconomics', 'ai_label': 'Other'}])
def test_invalid_or_conflicting_labels_return_422(client, params):
    assert client.get('/documents', params=params).status_code == 422
