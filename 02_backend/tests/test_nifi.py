"""Read-only NiFi contract, scope and failure boundaries."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from common import nifi

GROUP = '12345678-1234-1234-1234-123456789abc'
app = FastAPI()
app.include_router(nifi.router)
client = TestClient(app)


def test_sample_is_deterministic_and_offline(monkeypatch):
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: (_ for _ in ()).throw(AssertionError('network')))
    a = client.get('/api/nifi/snapshot').json()
    assert a == client.get('/api/nifi/snapshot?mode=sample').json()
    assert a['mode'] == 'sample' and a['metrics']['queued'] == 24
    assert client.post('/api/nifi/snapshot').status_code == 405
    assert client.get('/api/nifi/snapshot?mode=unknown').status_code == 422


def test_missing_live_never_returns_sample(monkeypatch):
    monkeypatch.delenv('NIFI_API_URL', raising=False)
    response = client.get('/api/nifi/snapshot?mode=live')
    assert response.status_code == 503 and 'processors' not in response.json()


def install_transport(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(nifi.httpx, 'AsyncClient', lambda **kw: real(**kw, transport=httpx.MockTransport(handler)))
    monkeypatch.setenv('NIFI_API_URL', 'https://nifi.example/nifi-api')
    monkeypatch.setenv('NIFI_PROCESS_GROUP_ID', 'root')
    monkeypatch.setenv('NIFI_TOKEN', 'private-value')


def test_live_scopes_projects_and_reads_only(monkeypatch):
    calls = []
    def handle(request):
        calls.append(request)
        assert request.method == 'GET'
        assert request.headers['authorization'] == 'Bearer private-value'
        if request.url.path.endswith('/root'):
            body = {'processGroupFlow': {'id': GROUP, 'flow': {'processors': [{'id': 'p', 'component': {
                'name': 'Reader', 'config': {'properties': {'password': 'never-return'}}, 'validationErrors': ['secret']}}],
                'processGroups': [{'id': 'child'}]}}}
        elif request.url.path.endswith('/status'):
            body = {'processGroupStatus': {'id': GROUP, 'aggregateSnapshot': {'name': 'Flow', 'flowFilesQueued': 7}}}
        else:
            assert re.fullmatch(request.url.params['groupId'], GROUP)
            assert not re.fullmatch(request.url.params['groupId'], GROUP + '-outside')
            body = {'bulletinBoard': {'bulletins': [{'bulletin': {'id': 1, 'groupId': GROUP, 'message': 'secret'}},
                                                   {'bulletin': {'id': 2, 'groupId': 'outside'}}]}}
        return httpx.Response(200, json=body)
    install_transport(monkeypatch, handle)
    result = client.get('/api/nifi/snapshot?mode=live')
    assert result.status_code == 200
    data = result.json()
    assert data['mode'] == 'live' and data['metrics']['queued'] == 7
    assert len(data['bulletins']) == 1
    assert data['processors'][0]['state'] == 'UNKNOWN'
    assert data['processors'][0]['threads'] is None
    assert len(calls) == 3
    assert all(s not in result.text for s in ('never-return', 'private-value', 'secret'))
    assert 'private-value' not in client.get('/api/nifi/config').text


def test_upstream_error_is_sanitized(monkeypatch):
    install_transport(monkeypatch, lambda req: httpx.Response(401, text='private-value'))
    result = client.get('/api/nifi/snapshot?mode=live')
    assert result.status_code == 502
    assert 'private-value' not in result.text and 'processors' not in result.json()


def test_group_mismatch_rejected(monkeypatch):
    install_transport(monkeypatch, lambda req: httpx.Response(200, json={'processGroupFlow': {'id': GROUP}}))
    monkeypatch.setenv('NIFI_PROCESS_GROUP_ID', 'aaaaaaaa-1234-1234-1234-123456789abc')
    assert client.get('/api/nifi/snapshot?mode=live').status_code == 502


def test_credentials_require_tls(monkeypatch):
    monkeypatch.setenv('NIFI_API_URL', 'http://nifi.example/nifi-api')
    monkeypatch.setenv('NIFI_TOKEN', 'secret')
    monkeypatch.setenv('NIFI_PROCESS_GROUP_ID', 'root')
    assert client.get('/api/nifi/snapshot?mode=live').status_code == 503


if __name__ == '__main__':
    assert nifi.sample_snapshot()['mode'] == 'sample'
