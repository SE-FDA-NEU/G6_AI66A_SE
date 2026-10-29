"""M4-02 / US05: real authentication and cross-account read protection.

Reuse conftest's SQLite database, temporary storage and recording queue.
No authentication dependency is replaced: requests exercise JWT verification.
"""
from datetime import datetime, timedelta
import secrets

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import SESSION_COOKIE, create_access_token, get_password_hash
from app.models import Document, FileFormat, Job, JobMode, JobStatus, User


@pytest.fixture
def login_user(session_factory):
    password = secrets.token_urlsafe(24)
    with session_factory() as db:
        user = db.get(User, 123)
        user.password_hash = get_password_hash(password)
        db.commit()
    return {'username': 'upload@example.com', 'password': password}


@pytest.mark.parametrize('identity', ['upload@example.com', 'upload_user'])
def test_login_accepts_email_and_username(client, login_user, identity):
    """TC-US05-01: valid credentials create a usable bearer and HttpOnly session."""
    client.headers.pop('Authorization')
    response = client.post('/auth/login', data={**login_user, 'username': identity})
    assert response.status_code == 200
    body = response.json()
    assert body['token_type'] == 'bearer'
    assert response.headers['cache-control'] == 'no-store'
    assert client.cookies.get(SESSION_COOKIE) == body['access_token']
    assert 'HttpOnly' in response.headers['set-cookie']
    expected = {'id': 123, 'username': 'upload_user', 'email': 'upload@example.com'}
    assert client.get('/auth/me').json() == expected
    client.cookies.clear()
    me = client.get('/auth/me', headers={'Authorization': f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json() == expected
    assert 'password' not in response.text and 'password_hash' not in me.text


@pytest.mark.parametrize('identity,password', [
    ('upload@example.com', 'incorrect-password'),
    ('unknown@example.com', 'US05-test-password'),
])
def test_bad_credentials_return_same_error_without_session(client, login_user, identity, password):
    """TC-US05-02: reject incorrect passwords and unknown accounts without disclosure."""
    client.headers.pop('Authorization')
    response = client.post('/auth/login', data={'username': identity, 'password': password})
    assert response.status_code == 401
    assert response.json() == {'detail': 'Email hoặc mật khẩu không đúng.'}
    assert response.headers['www-authenticate'] == 'Bearer'
    assert SESSION_COOKIE not in client.cookies
    assert 'set-cookie' not in response.headers


@pytest.mark.parametrize('path', ['/auth/me', '/documents', '/jobs', '/search?q=private'])
@pytest.mark.parametrize('token_kind', ['missing', 'forged', 'expired'])
def test_protected_routes_reject_invalid_sessions(client, path, token_kind):
    """TC-US05-03: missing, forged and expired JWTs never return protected data."""
    expired = jwt.encode({'sub': '123', 'exp': datetime.utcnow() - timedelta(minutes=1)},
                         settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    token = {'missing': '', 'forged': 'forged-token', 'expired': expired}[token_kind]
    client.headers.pop('Authorization')
    response = client.get(path, headers={'Authorization': f'Bearer {token}'} if token else {})
    assert response.status_code == 401
    assert response.json() == {'detail': 'Token không hợp lệ hoặc đã hết hạn'}
    assert response.headers['www-authenticate'] == 'Bearer'


@pytest.fixture
def private_resources(session_factory, tmp_path):
    source = tmp_path / 'private-contract.pdf'
    source.write_bytes(b'private-contract-file-content')
    with session_factory() as db:
        document = Document(owner_id=123, original_filename=source.name, storage_path=str(source),
                            file_format=FileFormat.PDF, file_size_bytes=source.stat().st_size,
                            extracted_text=[{'page': 1, 'text': 'private contract text'}],
                            expires_at=datetime.utcnow() + timedelta(days=30))
        job = Job(owner_id=123, mode=JobMode.BULLET, status=JobStatus.COMPLETED,
                  file_count=1, result_data={'summary': 'private job result'})
        db.add_all([document, job])
        db.commit()
        return document.id, job.id, str(source), document.last_accessed_at, document.expires_at


def test_owner_reads_resources_but_other_account_cannot(client, session_factory, private_resources):
    """TC-US05-04: B cannot retrieve A's metadata, file, extracted text or job result."""
    document_id, job_id, storage_path, _, _ = private_resources
    assert client.get(f'/documents/{document_id}').json()['original_filename'] == 'private-contract.pdf'
    assert client.get(f'/jobs/{job_id}').json()['result_data'] == {'summary': 'private job result'}
    with session_factory() as db:
        document = db.get(Document, document_id)
        before = (document.last_accessed_at, document.expires_at)
    other = {'Authorization': f"Bearer {create_access_token({'sub': '124'})}"}
    for path, status, detail in [
        (f'/documents/{document_id}', 403, 'Access denied'),
        (f'/documents/{document_id}/file', 403, 'Access denied'),
        (f'/documents/{document_id}/pages', 403, 'Access denied'),
        (f'/jobs/{job_id}', 404, f'Job with ID {job_id} not found'),
        (f'/jobs/{job_id}/export.pdf', 404, f'Job with ID {job_id} not found'),
    ]:
        response = client.get(path, headers=other)
        assert response.status_code == status
        assert response.json() == {'detail': detail}
        for secret in ('private-contract', 'private contract text', 'private job result', storage_path):
            assert secret not in response.text
    assert client.get('/documents', headers=other).json() == []
    assert client.get('/jobs', headers=other).json() == []
    with session_factory() as db:
        document = db.get(Document, document_id)
        assert (document.last_accessed_at, document.expires_at) == before
