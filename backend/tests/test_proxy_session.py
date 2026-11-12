"""Deployment contract: trust HTTPS headers only from configured proxy peers."""
import secrets

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.main import app
from app.models import User
from app.core.security import get_password_hash


@pytest.mark.parametrize('trusted,secure', [(True, True), (False, False)])
def test_forwarded_https_session_cookie(client, session_factory, trusted, secure):
    # The client fixture supplies isolated SQLite and dependency overrides.
    credential = secrets.token_urlsafe(24)
    with session_factory() as db:
        db.get(User, 123).password_hash = get_password_hash(credential)
        db.commit()
    proxy = ProxyHeadersMiddleware(app, trusted_hosts=['testclient'] if trusted else [])
    with TestClient(proxy) as browser:
        response = browser.post('/auth/login',
                                data={'username': 'upload@example.com', 'password': credential},
                                headers={'X-Forwarded-Proto': 'https'})
        assert response.status_code == 200
        cookie = response.headers['set-cookie']
        assert ('; Secure' in cookie) is secure
        assert '; HttpOnly' in cookie and '; SameSite=lax' in cookie
        assert 'Domain=' not in cookie
        assert response.headers['cache-control'] == 'no-store'
