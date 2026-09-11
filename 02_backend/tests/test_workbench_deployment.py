"""Deployment contract tests: no live credentials or project mutations."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '02_backend'))
sys.path.insert(0, str(ROOT / 'cai_integration'))

import importlib.util
import json
import httpx
import pytest
from client import Client, normalize_host
from deploy_application import build_payload, deploy
from setup_project import setup, project_payload
from bootstrap import prepare, job_payload
from validate_amp import validate as validate_amp


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_notebook_cell(path):
    namespace = {'__name__': 'workbench_session'}
    source = (ROOT / path).read_text()
    exec(compile(source, '<workbench-session>', 'exec'), namespace)
    return namespace


def test_private_payload_no_deployment_credentials(monkeypatch):
    monkeypatch.setenv('CML_API_KEY', 'never-propagate')
    payload = build_payload('python-runtime')
    assert payload['bypass_authentication'] is False
    assert payload['script'] == '03_frontend/start_frontend.py'
    assert 'never-propagate' not in json.dumps(payload)
    assert 'CDSW_APP_PORT' not in payload['environment']
    with pytest.raises(ValueError):
        build_payload('')
    with pytest.raises(ValueError):
        build_payload('rt', '../invalid')


def test_amp_manifest_has_ordered_runnable_tasks():
    metadata = validate_amp()
    assert metadata['tasks'][-1]['type'] == 'start_application'


@pytest.mark.parametrize(
    ('path', 'root_name'),
    [
        ('02_backend/scripts/prepare.py', 'PROJECT_ROOT'),
        ('cai_integration/smoke_test.py', 'ROOT'),
    ],
)
def test_amp_session_entrypoints_do_not_require_file(path, root_name, monkeypatch):
    monkeypatch.delenv('CDSW_PROJECT_HOME', raising=False)
    monkeypatch.chdir(ROOT)
    namespace = load_notebook_cell(path)
    assert Path(namespace[root_name]) == ROOT


def test_host_and_git_validation():
    assert normalize_host('https://ml.example.com/api/v2/') == 'https://ml.example.com'
    for bad in ('http://ml.example.com', 'https://user:key@ml.example.com', 'https://ml.example.com/path'):
        with pytest.raises(ValueError):
            normalize_host(bad)
    assert project_payload('NPI', 'https://example.com/project.git')['project_visibility'] == 'private'
    with pytest.raises(ValueError):
        project_payload('NPI', 'https://token@example.com/project.git')


def test_pagination_and_http_error_not_empty_list():
    def handler(request):
        if request.url.path.endswith('/bad'):
            return httpx.Response(403, text='secret-key')
        if request.url.params.get('page_token'):
            return httpx.Response(200, json={'applications': [{'id': 'second'}]})
        return httpx.Response(200, json={'applications': [{'id': 'first'}], 'next_page_token': 'next'})
    client = Client('https://example.com', 'secret-key', httpx.MockTransport(handler))
    try:
        assert len(client.list('applications', 'applications')) == 2
        with pytest.raises(RuntimeError, match='HTTP 403') as err:
            client.list('bad', 'applications')
        assert 'secret-key' not in str(err.value)
    finally:
        client.close()


class FakeClient:
    def __init__(self, apps=None, status='running'):
        self.apps = apps or []
        self.calls = []
        self.status = status
    def list(self, path, key):
        return self.apps if key == 'applications' else []
    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == 'GET' and self.apps:
            return self.apps[0]
        return {'id': 'app-1'}
    def wait(self, path, success, failure, timeout=600, **kwargs):
        if self.status in failure:
            raise RuntimeError('failed')
        return {'status': self.status, 'url': 'https://npi.example.com'}


def test_create_and_restart_are_scoped():
    payload = build_payload('rt')
    client = FakeClient()
    result = deploy(client, 'project', payload)
    assert result['application_id'] == 'app-1' and not result['health_verified']
    assert client.calls[0][0] == 'POST'
    client = FakeClient([{**payload, 'id': 'app-1'}])
    deploy(client, 'project', payload)
    assert client.calls[-1][1].endswith('/app-1:restart')
    assert not any(c[0] == 'DELETE' for c in client.calls)


def test_config_drift_and_duplicates_do_not_mutate():
    payload = build_payload('rt')
    for apps in ([{**payload, 'id': 'a', 'script': 'wrong.py'}],
                 [{**payload, 'id': 'a'}, {**payload, 'id': 'b'}]):
        client = FakeClient(apps)
        with pytest.raises(RuntimeError):
            deploy(client, 'p', payload)
        assert all(c[0] == 'GET' for c in client.calls)


def test_wait_terminal_failure_and_timeout():
    client = Client('https://example.com', 'key', httpx.MockTransport(lambda r: httpx.Response(200, json={'status': 'failed'})))
    try:
        with pytest.raises(RuntimeError, match='failed'):
            client.wait('jobs/id', {'succeeded'}, {'failed'})
        with pytest.raises(TimeoutError):
            client.wait('jobs/id', {'succeeded'}, {'failed'}, timeout=0)
    finally:
        client.close()


def test_prepare_tracks_exact_run():
    client = FakeClient(status='succeeded')
    result = prepare(client, 'p', job_payload('rt'))
    assert result['run_id'] == 'app-1'
    assert client.calls[-1][1].endswith('/jobs/app-1/runs')


def test_preparation_failure_propagates():
    with pytest.raises(RuntimeError):
        prepare(FakeClient(status='failed'), 'p', job_payload('rt'))


def test_launcher_port_priority_and_import_is_safe(monkeypatch):
    module = load_file('npi_launcher', '03_frontend/start_frontend.py')
    monkeypatch.setenv('CDSW_APP_PORT', '8090')
    monkeypatch.setenv('FRONTEND_PORT', '8100')
    assert module._env_int('CDSW_APP_PORT', 'FRONTEND_PORT', default=1) == 8090
    assert module._backend_proc is None
    monkeypatch.setenv('CDSW_APP_PORT', 'broken')
    with pytest.raises(ValueError):
        module._env_int('CDSW_APP_PORT', default=1)


def test_launcher_fails_on_dead_backend():
    module = load_file('npi_launcher_dead', '03_frontend/start_frontend.py')
    class Dead:
        def poll(self): return 1
    module._backend_proc = Dead()
    with pytest.raises(RuntimeError, match='exited'):
        module._wait_for_backend(1)


def test_installer_preserves_config(tmp_path, monkeypatch):
    module = load_file('npi_installer', '01_installer/install.py')
    monkeypatch.setattr(module, 'PROJECT_ROOT', str(tmp_path))
    (tmp_path / 'config').mkdir()
    config = tmp_path / 'config/config.yaml'
    (tmp_path / 'config/config.yaml.example').write_text('default')
    module.initialize_config()
    assert config.read_text() == 'default'
    config.write_text('custom')
    module.initialize_config()
    assert config.read_text() == 'custom'
    assert module.node_supported('v22.12.0') and not module.node_supported('v22.11.0')


if __name__ == '__main__':
    assert build_payload('test')['bypass_authentication'] is False
