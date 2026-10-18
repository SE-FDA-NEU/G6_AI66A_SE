"""Owned folders and membership changes preserve all extracted/AI metadata."""
from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from app.core.security import create_access_token
from app.models import Document, FileFormat, Folder, ReviewState
from app.services.reader_extraction import extract_document_for_reader
from test_pdf_extraction import make_pdf


def headers(owner):
    return {'Authorization': f"Bearer {create_access_token({'sub': str(owner)})}"}


@pytest.fixture
def filed_documents(session_factory, tmp_path):
    source = make_pdf(tmp_path / 'filed.pdf', [b'BT /F1 12 Tf 30 720 Td (Payment penalty 0.05% per day.) Tj ET'])
    with session_factory() as db:
        first = Folder(owner_id=123, name='First')
        second = Folder(owner_id=123, name='Second')
        private = Folder(owner_id=124, name='Private folder')
        db.add_all([first, second, private])
        db.flush()
        own = Document(owner_id=123, folder_id=first.id, original_filename='contract.pdf',
                       storage_path=str(source), file_format=FileFormat.PDF,
                       file_size_bytes=source.stat().st_size, ai_label='Contract', ai_confidence=.91,
                       user_label='Supplier agreement', review_state=ReviewState.CONFIRMED,
                       last_accessed_at=datetime(2026, 1, 1), expires_at=datetime.utcnow() + timedelta(days=30))
        peer = Document(owner_id=124, folder_id=private.id, original_filename='private.pdf',
                        storage_path=str(source), file_format=FileFormat.PDF,
                        file_size_bytes=source.stat().st_size, ai_label='Report', ai_confidence=.72,
                        review_state=ReviewState.NEEDS_REVIEW, expires_at=datetime.utcnow() + timedelta(days=30))
        db.add_all([own, peer])
        db.commit()
        ids = {'first': first.id, 'second': second.id, 'private': private.id, 'own': own.id, 'peer': peer.id}
    extract_document_for_reader(ids['own'], session_factory)
    return ids


def snapshot(document):
    return {column.name: deepcopy(getattr(document, column.name)) for column in Document.__table__.columns}


def test_create_and_list_folders_are_persisted_owner_scoped_and_paginated(client, session_factory):
    assert client.get('/folders').json() == []
    created = client.post('/folders', json={'name': '  Hợp đồng nhà cung cấp  '})
    assert created.status_code == 201
    folder = created.json()
    assert folder['owner_id'] == 123 and folder['name'] == 'Hợp đồng nhà cung cấp'
    assert datetime.fromisoformat(folder['created_at'])
    second = client.post('/folders', json={'name': 'Invoices'}).json()
    peer = client.post('/folders', json={'name': 'Private'}, headers=headers(124))
    assert peer.status_code == 201
    assert client.get('/folders?owner_id=124').json() == [second, folder]
    assert client.get('/folders?limit=1').json() == [second]
    assert client.get('/folders?limit=1&skip=1').json() == [folder]
    assert client.get('/folders?skip=2').json() == []
    assert client.get('/folders', headers=headers(124)).json() == [peer.json()]
    with session_factory() as db:
        saved = db.get(Folder, folder['id'])
        assert saved.owner_id == 123 and saved.name == folder['name']


@pytest.mark.parametrize('payload', [
    {}, {'name': ''}, {'name': ' \t\n'}, {'name': 'x' * 101}, {'name': None}, {'name': 123},
    {'name': True}, {'name': ['folder']}, {'name': 'Valid', 'owner_id': 124},
])
def test_invalid_folder_creation_cannot_create_or_spoof_owner(client, session_factory, payload):
    assert client.post('/folders', json=payload).status_code == 422
    with session_factory() as db:
        assert db.query(Folder).count() == 0


def test_folder_name_accepts_storage_boundary(client):
    response = client.post('/folders', json={'name': 'x' * 100})
    assert response.status_code == 201 and len(response.json()['name']) == 100


@pytest.mark.parametrize('params', [{'skip': -1}, {'limit': 0}, {'limit': 101}, {'limit': 'invalid'}])
def test_invalid_folder_list_pagination(client, params):
    assert client.get('/folders', params=params).status_code == 422


def test_move_and_unfile_change_only_membership_and_existing_search_filters_see_the_move(client, session_factory, filed_documents):
    ids = filed_documents
    with session_factory() as db:
        before = snapshot(db.get(Document, ids['own']))
    for folder_id in [ids['second'], None, None, ids['first']]:
        moved = client.patch(f"/documents/{ids['own']}/folder", json={'folder_id': folder_id})
        assert moved.status_code == 200
        assert moved.json()['folder_id'] == folder_id
        assert moved.json()['ai_label'] == 'Contract' and moved.json()['ai_confidence'] == .91
        assert moved.json()['user_label'] == 'Supplier agreement' and moved.json()['review_state'] == 'confirmed'
        with session_factory() as db:
            after = snapshot(db.get(Document, ids['own']))
            unchanged = set(before) - {'folder_id', 'last_accessed_at', 'expires_at'}
            assert {key: after[key] for key in unchanged} == {key: before[key] for key in unchanged}
            assert after['folder_id'] == folder_id
            assert after['expires_at'] - after['last_accessed_at'] == timedelta(days=30)
        for candidate in [ids['first'], ids['second']]:
            listed = client.get('/documents', params={'folder_id': candidate}).json()
            assert [doc['id'] for doc in listed] == ([ids['own']] if folder_id == candidate else [])
            result = client.get('/search', params={'q': 'payment penalty', 'folder_id': candidate}).json()
            assert result['total_hits'] == (1 if folder_id == candidate else 0)
        all_hits = client.get('/search?q=payment%20penalty').json()['hits']
        assert len(all_hits) == 1 and all_hits[0]['folder_id'] == folder_id


@pytest.mark.parametrize('document,folder,expected', [
    ('own', 'private', 403), ('peer', 'first', 403), ('peer', 'private', 403),
    ('peer', None, 403), ('missing', 'first', 404), ('own', 'missing', 404),
])
def test_rejected_moves_leave_both_accounts_unchanged(client, session_factory, filed_documents, document, folder, expected):
    ids = {**filed_documents, 'missing': 99999}
    with session_factory() as db:
        before = [snapshot(db.get(Document, ids[key])) for key in ['own', 'peer']]
    response = client.patch(f'/documents/{ids[document]}/folder',
                            json={'folder_id': ids[folder] if folder is not None else None})
    assert response.status_code == expected
    assert 'private.pdf' not in response.text and 'Private folder' not in response.text
    with session_factory() as db:
        assert [snapshot(db.get(Document, ids[key])) for key in ['own', 'peer']] == before


@pytest.mark.parametrize('payload', [
    {}, {'folder_id': 0}, {'folder_id': -1}, {'folder_id': True}, {'folder_id': '1'},
    {'folder_id': 1.5}, {'folder_id': 2147483648}, {'folder_id': []},
    {'folder_id': None, 'ai_label': 'Changed'}, {'folder_id': None, 'user_label': 'Changed'},
    {'folder_id': None, 'ai_confidence': .1}, {'folder_id': None, 'owner_id': 124},
])
def test_invalid_moves_cannot_clear_membership_or_edit_metadata(client, session_factory, filed_documents, payload):
    document_id = filed_documents['own']
    with session_factory() as db:
        before = snapshot(db.get(Document, document_id))
    assert client.patch(f'/documents/{document_id}/folder', json=payload).status_code == 422
    with session_factory() as db:
        assert snapshot(db.get(Document, document_id)) == before


def test_folder_and_move_endpoints_require_authentication(client, filed_documents):
    invalid = {'Authorization': 'Bearer invalid'}
    assert client.get('/folders', headers=invalid).status_code == 401
    assert client.post('/folders', headers=invalid, json={'name': 'Invalid'}).status_code == 401
    assert client.patch(f"/documents/{filed_documents['own']}/folder", headers=invalid,
                        json={'folder_id': None}).status_code == 401
    assert client.get('/folders', headers=headers(99999)).status_code == 401
    assert client.post('/folders', headers=headers(99999), json={'name': 'Ghost'}).status_code == 401
