"""Encrypted account keys persist, stay isolated, and can be replaced/deleted."""
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.core.security import create_access_token
from app.models import User
from app.services.saved_api_keys import decrypt_key


def test_saved_key_is_encrypted_and_used_by_later_uploads(client, session_factory, job_queue, monkeypatch):
    client.headers.pop('X-Gemini-Api-Key', None)
    captured = []
    monkeypatch.setattr(job_queue, 'enqueue', lambda job_id, *, gemini_api_key: captured.append(gemini_api_key.get_secret_value()))
    assert client.get('/auth/gemini-key').json() == {'configured': False}
    for key in ('first-private-key', 'replacement-private-key'):
        saved = client.put('/auth/gemini-key', json={'api_key': key})
        assert saved.json() == {'configured': True}
        assert saved.headers['cache-control'] == 'no-store'
        with session_factory() as db:
            user = db.get(User, 123)
            assert key not in user.gemini_api_key_encrypted
            assert decrypt_key(user).get_secret_value() == key
        assert client.get('/auth/gemini-key').json() == {'configured': True}
        assert key not in client.get('/auth/me').text
        upload = client.post('/upload', files={'files': ('report.pdf', b'%PDF-test')})
        assert upload.status_code == 202
        assert captured[-1] == key
        assert key not in client.get(f"/jobs/{upload.json()['jobId']}").text
    assert captured == ['first-private-key', 'replacement-private-key']
    assert client.delete('/auth/gemini-key').status_code == 204
    assert client.get('/auth/gemini-key').json() == {'configured': False}
    assert client.post('/upload', files={'files': ('report.pdf', b'%PDF-test')}).status_code == 400


def test_keys_are_owned_by_account_and_cannot_be_swapped(client, session_factory):
    assert client.put('/auth/gemini-key', json={'api_key': 'owner-key'}).status_code == 200
    other = {'Authorization': f"Bearer {create_access_token({'sub': '124'})}"}
    assert client.get('/auth/gemini-key', headers=other).json() == {'configured': False}
    assert client.put('/auth/gemini-key', headers=other, json={'api_key': 'other-key'}).status_code == 200
    assert client.delete('/auth/gemini-key', headers=other).status_code == 204
    assert client.get('/auth/gemini-key').json() == {'configured': True}
    with session_factory() as db:
        db.get(User, 124).gemini_api_key_encrypted = db.get(User, 123).gemini_api_key_encrypted
        db.commit()
    client.headers.pop('X-Gemini-Api-Key', None)
    response = client.post('/upload', headers=other, files={'files': ('source.pdf', b'%PDF-test')})
    assert response.status_code == 409
    assert 'owner-key' not in response.text


@pytest.mark.parametrize('body', [{}, {'api_key': 123}, {'api_key': ['private-value']}])
def test_validation_never_echoes_key_payload(client, body):
    result = client.put('/auth/gemini-key', json=body)
    assert result.status_code == 422
    assert result.json() == {'detail': 'Invalid API key request.'}


def test_invalid_replacement_preserves_previous_key(client, session_factory):
    client.put('/auth/gemini-key', json={'api_key': 'valid-previous'})
    assert client.put('/auth/gemini-key', json={'api_key': 'bad key'}).status_code == 400
    with session_factory() as db:
        assert decrypt_key(db.get(User, 123)).get_secret_value() == 'valid-previous'


def test_guests_cannot_manage_keys(client):
    client.headers.pop('Authorization')
    for method in ('get', 'put', 'delete'):
        response = getattr(client, method)('/auth/gemini-key', **({'json': {'api_key': 'private-key'}} if method == 'put' else {}))
        assert response.status_code == 401


def test_additive_migration_preserves_old_accounts_and_is_idempotent():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
    from add_saved_gemini_key import migrate
    engine = create_engine('sqlite://')
    with engine.begin() as db:
        db.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(100))'))
        db.execute(text("INSERT INTO users (id, username) VALUES (1, 'existing')"))
    assert migrate(engine)
    assert not migrate(engine)
    with engine.connect() as db:
        assert tuple(db.execute(text('SELECT id, username, gemini_api_key_encrypted FROM users')).one()) == (1, 'existing', None)
    engine.dispose()
