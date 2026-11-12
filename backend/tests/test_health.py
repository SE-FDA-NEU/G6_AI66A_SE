import asyncio
import logging
import threading

import pytest

from app.main import app
from app.services.health import HealthProbe, get_health_probe


@pytest.mark.parametrize('healthy, expected', [(True, 200), (False, 503)])
def test_health_checks_db_without_auth_or_sensitive_details(client, monkeypatch, healthy, expected):
    client.headers.pop('Authorization')
    def query():
        if not healthy:
            raise RuntimeError('mysql://private-user:private-password@db/source-text')
        return True
    app.dependency_overrides[get_health_probe] = lambda: HealthProbe(query)
    response = client.get('/health')
    assert response.status_code == expected
    assert response.headers['cache-control'] == 'no-store'
    assert response.json() == {
        'status': 'ok' if healthy else 'unavailable',
        'database': 'ready' if healthy else 'unavailable'}
    assert 'private' not in response.text


def test_probe_deadline_does_not_accumulate_workers_and_recovers():
    release = threading.Event()
    calls = []
    def blocked_query():
        calls.append(1)
        release.wait(2)
        return True
    async def scenario():
        probe = HealthProbe(blocked_query, timeout=.02)
        try:
            assert not await probe.ready()
            assert not await probe.ready()
            assert calls == [1]
        finally:
            release.set()
        assert await probe.pending
        assert await probe.ready()
        assert len(calls) == 2
    asyncio.run(scenario())


def test_endpoint_returns_503_on_probe_timeout(client):
    class SlowProbe:
        async def ready(self):
            probe = HealthProbe(lambda: threading.Event().wait(.04), timeout=.01)
            result = await probe.ready()
            await probe.pending
            return result
    app.dependency_overrides[get_health_probe] = SlowProbe
    assert client.get('/health').status_code == 503


def test_request_metrics_do_not_log_url_queries_or_secrets(client, caplog):
    with caplog.at_level(logging.INFO, logger='app.operations'):
        assert client.get('/?q=private-document-text', headers={'X-Private': 'private-key'}).status_code == 200
        assert client.get('/unknown-private-user?q=private-token').status_code == 404
    events = '\n'.join(record.getMessage() for record in caplog.records if record.name == 'app.operations')
    assert 'status=200' in events and 'status=404' in events
    assert 'duration_ms=' in events and 'route=<unmatched>' in events
    assert 'private-' not in events
