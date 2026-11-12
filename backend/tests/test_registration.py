"""Public registration uses real hashing, unique identities and isolated sessions."""
import secrets

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security import SESSION_COOKIE, verify_password
from app.models import User


@pytest.fixture
def registration(client):
    client.headers.pop('Authorization', None)
    return {'username': 'new_member', 'email': 'new.member@example.com',
            'password': secrets.token_urlsafe(18)}


def test_register_hashes_password_and_creates_private_session(client, session_factory, registration):
    payload = {**registration, 'username': ' New_Member ', 'email': ' NEW.MEMBER@EXAMPLE.COM '}
    response = client.post('/auth/register', json=payload)
    assert response.status_code == 201
    assert response.headers['cache-control'] == 'no-store'
    assert 'HttpOnly' in response.headers['set-cookie']
    assert client.cookies.get(SESSION_COOKIE) == response.json()['access_token']
    with session_factory() as db:
        user = db.query(User).filter_by(username='new_member').one()
        assert user.email == registration['email']
        assert user.password_hash != registration['password']
        assert verify_password(registration['password'], user.password_hash)
        user_id = user.id
    assert client.get('/auth/me').json() == {
        'id': user_id, 'username': 'new_member', 'email': registration['email']}
    assert client.get('/documents').json() == []
    assert client.get('/jobs').json() == []
    assert registration['password'] not in response.text
    assert 'password_hash' not in response.text
    client.post('/auth/logout')
    assert client.get('/auth/me').status_code == 401
    for identity in ('NEW.MEMBER@EXAMPLE.COM', 'NEW_MEMBER'):
        assert client.post('/auth/login', data={
            'username': identity, 'password': registration['password']}).status_code == 200


@pytest.mark.parametrize('changes', [
    {'email': 'UPLOAD@EXAMPLE.COM'}, {'username': 'UPLOAD_USER'},
])
def test_duplicate_identity_does_not_create_account_or_session(client, session_factory, registration, changes):
    response = client.post('/auth/register', json={**registration, **changes})
    assert response.status_code == 409
    assert SESSION_COOKIE not in client.cookies
    with session_factory() as db:
        assert db.query(User).count() == 2


@pytest.mark.parametrize('changes', [
    {'username': 'ab'}, {'username': 'a' * 101}, {'username': 'name@example.com'},
    {'username': 'has spaces'}, {'email': 'invalid'}, {'password': 'a' * 7},
    {'password': ' ' * 8}, {'password': 'a' * 73}, {'password': 'é' * 37},
    {'role': 'admin'}, {'password': None},
])
def test_invalid_registration_has_no_side_effects(client, session_factory, registration, changes):
    response = client.post('/auth/register', json={**registration, **changes})
    assert response.status_code == 422
    assert response.json() == {'detail': 'Thông tin đăng ký không hợp lệ. Vui lòng kiểm tra lại.'}
    assert SESSION_COOKIE not in client.cookies
    with session_factory() as db:
        assert db.query(User).count() == 2


@pytest.mark.parametrize('value', ['a' * 8, 'a' * 72, 'é' * 36])
def test_password_boundaries_are_usable_for_login(client, registration, value):
    assert client.post('/auth/register', json={**registration, 'password': value}).status_code == 201
    client.post('/auth/logout')
    assert client.post('/auth/login', data={'username': registration['email'], 'password': value}).status_code == 200


def test_concurrent_unique_conflict_is_rolled_back(client, session_factory, registration, monkeypatch):
    def conflict(_):
        raise IntegrityError('insert', {}, Exception('private DB details'))
    monkeypatch.setattr(session_factory.class_, 'commit', conflict)
    response = client.post('/auth/register', json=registration)
    assert response.status_code == 409
    assert 'private DB details' not in response.text
    assert SESSION_COOKIE not in client.cookies
    with session_factory() as db:
        assert db.query(User).count() == 2


def test_registration_cookie_is_secure_over_https(client, registration):
    response = client.post('https://testserver/auth/register', json=registration)
    assert response.status_code == 201
    assert 'Secure' in response.headers['set-cookie']
