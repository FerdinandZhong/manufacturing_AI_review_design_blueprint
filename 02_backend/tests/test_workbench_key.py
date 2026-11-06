"""Caller-key validation, permission enforcement, redaction and signed-hop checks."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from common import db, workbench_key
from common.security import forwarded_identity
from api.main import app


@pytest.fixture
def platform(monkeypatch, tmp_path):
    monkeypatch.setenv('NPI_AUTH_MODE', 'workbench')
    monkeypatch.setenv('NPI_PUBLIC_ORIGIN', 'https://npi.example.com')
    monkeypatch.setenv('CDSW_DOMAIN', 'workbench.example.com')
    monkeypatch.setenv('CDSW_PROJECT_ID', 'vehicle-project')
    monkeypatch.setenv('NPI_INGRESS_SECRET', 'test-secret')
    monkeypatch.setenv('NPI_TRUSTED_PROXY_CIDRS', '127.0.0.1/32')
    monkeypatch.setenv('CDSW_APIV2_KEY', 'server-key-must-never-be-used')
    monkeypatch.setattr(db, 'get_db_path', lambda: str(tmp_path/'ops.db'))
    db.init_db()
    state = {'status':200, 'body':{'id':'vehicle-project', 'permissions':{'read':True, 'write':False}},
             'identity':{'valid':True,'username':'verified-user'}, 'calls':[], 'identity_calls':[]}
    real_client = httpx.Client

    def respond(request):
        assert request.headers['authorization'] == 'Bearer caller-key'
        if request.url.path == '/api/v2/auth/validate_key':
            state['identity_calls'].append(request)
            assert request.method == 'POST' and b'"API"' in request.content
            return httpx.Response(state.get('identity_status',200),json=state['identity'])
        state['calls'].append(request)
        assert str(request.url) == 'https://workbench.example.com/api/v2/projects/vehicle-project'
        if state.get('failure'):
            raise httpx.ConnectError('sensitive transport failure', request=request)
        return httpx.Response(state['status'], json=state['body'], headers={'location':'https://untrusted.example'})

    def client(**kwargs):
        assert kwargs['follow_redirects'] is False and kwargs['trust_env'] is False
        assert kwargs['timeout'] == 5.0
        return real_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(workbench_key.httpx, 'Client', client)
    return state


def request(headers=None, method='GET', path='/api/runtime/status', peer='127.0.0.1'):
    return Request({'type':'http', 'scheme':'http', 'method':method, 'path':path,
                    'query_string':b'', 'client':(peer, 1234), 'server':('127.0.0.1',8100),
                    'headers':headers if headers is not None else [(b'authorization',b'Bearer caller-key')]})


def test_single_key_signed_hop_read_and_ro_mutation_denial(platform):
    frontend_request = request()
    signed = forwarded_identity(frontend_request, 'test-secret')
    actor = 'verified-user'
    assert signed['x-npi-actor'] == actor
    assert signed['x-npi-permission'] == 'RO'
    assert signed['x-npi-auth-kind'] == 'machine'
    backend = TestClient(app, client=('127.0.0.1',1234))
    response = backend.get('/api/runtime/status', headers=signed)
    assert response.status_code == 200 and response.json()['identity']['actor'] == actor
    path = '/api/config/llm/models'
    signed = forwarded_identity(request(method='POST',path=path), 'test-secret')
    assert backend.post(path, json={}, headers=signed).status_code == 403
    with db.get_connection() as conn:
        event = dict(conn.execute('SELECT * FROM audit_events ORDER BY event_id DESC LIMIT 1').fetchone())
    assert event['actor'] == actor and event['outcome'] == 'authorization_denied'
    assert 'caller-key' not in str(event) and 'server-key' not in str(event)


@pytest.mark.parametrize('permissions', [{'read':True,'write':True}, {'read':True,'admin':True}])
def test_rw_permission_and_csrf_preserved(platform, permissions):
    platform['body']['permissions'] = permissions
    path = '/api/config/llm/models'
    backend = TestClient(app, client=('127.0.0.1',1234))
    signed = forwarded_identity(request(method='POST',path=path), 'test-secret')
    assert backend.post(path, json={}, headers=signed).status_code == 422
    native = [(b'authorization',b'Bearer caller-key'), (b'origin',b'https://evil.example')]
    signed = forwarded_identity(request(native,method='POST',path=path), 'test-secret')
    assert backend.post(path,json={},headers={**signed,'origin':'https://evil.example'}).status_code == 403


@pytest.mark.parametrize('status', [301,302,401,403,404,429,500])
def test_platform_rejects_and_redirects_fail_closed(platform, status):
    platform['status'] = status
    with pytest.raises(PermissionError) as error:
        forwarded_identity(request(), 'test-secret')
    assert 'caller-key' not in str(error.value)
    assert len(platform['calls']) == 1


@pytest.mark.parametrize('body', [None, [], {}, {'id':'other-project','permissions':{'read':True}},
    {'id':'vehicle-project','permissions':{'write':True}},
    {'id':'vehicle-project','permissions':{'read':'true'}},
    {'id':'vehicle-project','permissions':None}])
def test_malformed_project_and_missing_read_fail_closed(platform, body):
    platform['body'] = body
    with pytest.raises(PermissionError):
        forwarded_identity(request(), 'test-secret')


def test_permission_revocation_is_immediate(platform):
    assert forwarded_identity(request(), 'test-secret')['x-npi-permission'] == 'RO'
    platform['status'] = 403
    with pytest.raises(PermissionError):
        forwarded_identity(request(), 'test-secret')
    assert len(platform['calls']) == 2


def test_network_failure_redacts_details(platform):
    platform['failure'] = True
    with pytest.raises(PermissionError, match='validation is unavailable') as error:
        forwarded_identity(request(), 'test-secret')
    assert 'sensitive' not in str(error.value)


@pytest.mark.parametrize('identity', [None, {}, {'valid':False,'username':'claimed-user'},
    {'valid':'true','username':'claimed-user'}, {'valid':True}, {'valid':True,'username':''},
    {'valid':True,'username':'\nforged'}, {'valid':True,'username':'x'*257}])
def test_invalid_user_validation_fails_before_project_lookup(platform, identity):
    platform['identity'] = identity
    with pytest.raises(PermissionError):
        forwarded_identity(request(), 'test-secret')
    assert not platform['calls']


@pytest.mark.parametrize('status', [302,401,403,500])
def test_user_validation_status_fails_closed(platform, status):
    platform['identity_status'] = status
    with pytest.raises(PermissionError):
        forwarded_identity(request(), 'test-secret')
    assert not platform['calls']


def test_client_native_identity_cannot_elevate_bearer(platform):
    h = [(b'authorization',b'Bearer caller-key'), (b'remote-user',b'claimed-admin'), (b'remote-user-perm',b'RW')]
    signed = forwarded_identity(request(h), 'test-secret')
    assert signed['x-npi-permission'] == 'RO'
    assert signed['x-npi-actor'] != 'claimed-admin'
    platform['status'] = 401
    with pytest.raises(PermissionError):
        forwarded_identity(request(h), 'test-secret')


@pytest.mark.parametrize('headers', [[], [(b'authorization',b'Basic key')],
    [(b'authorization',b'Bearer caller-key'),(b'authorization',b'Bearer second-key')],
    [(b'authorization',b'Bearer bad key')], [(b'authorization',b'Bearer ')],
    [(b'authorization',b'Bearer caller-key'),(b'remote_user',b'forged')]])
def test_missing_malformed_duplicate_credentials_fail_before_network(platform, headers):
    with pytest.raises(PermissionError):
        forwarded_identity(request(headers), 'test-secret')
    assert not platform['calls']


def test_untrusted_peer_fails_before_network(platform):
    with pytest.raises(PermissionError,match='Untrusted'):
        forwarded_identity(request(peer='203.0.113.1'), 'test-secret')
    assert not platform['calls']


@pytest.mark.parametrize('name,value', [('CDSW_DOMAIN','evil.example/path'),('CDSW_DOMAIN','evil.example@workbench.example'),
    ('CDSW_DOMAIN','https://workbench.example'), ('CDSW_PROJECT_ID','../other'), ('CDSW_PROJECT_ID','')])
def test_unsafe_destination_configuration(platform, monkeypatch, name, value):
    monkeypatch.setenv(name,value)
    with pytest.raises(PermissionError):
        forwarded_identity(request(), 'test-secret')
    assert not platform['calls']


if __name__ == '__main__':
    assert callable(test_single_key_signed_hop_read_and_ro_mutation_denial)
    print('Workbench key security checks available through pytest')
