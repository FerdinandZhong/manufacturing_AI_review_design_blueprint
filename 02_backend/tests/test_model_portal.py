"""Registry operations use isolated SQLite and never contact an external LLM."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from common import db
from agents import llm_client
from api.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'get_db_path', lambda: str(tmp_path / 'models.db'))
    db.init_db()
    with TestClient(app) as client:
        yield client


def register(client, alias='local'):
    return client.post('/api/config/llm/models', json={
        'alias': alias, 'provider': 'vllm', 'model_identifier': 'demo-model',
        'api_base': 'http://localhost:8000/v1', 'api_key': 'secret-key-1234',
    })


def test_register_edit_activate_and_mask(client):
    assert register(client).status_code == 200
    rows = client.get('/api/config/llm/models').json()['models']
    assert len(rows) == 1 and rows[0]['is_active'] == 1
    assert 'secret-key' not in rows[0]['api_key']
    model_id = rows[0]['id']
    assert llm_client._resolve_registered()['api_key'] == 'secret-key-1234'
    assert client.put(f'/api/config/llm/models/{model_id}', json={'alias': 'edited', 'api_key': ''}).status_code == 200
    resolved = llm_client._resolve_registered()
    assert resolved['api_key'] == 'secret-key-1234'
    assert resolved['base_url'] == 'http://localhost:8000/v1'
    assert register(client, 'second').status_code == 200
    assert client.post(f'/api/config/llm/models/{model_id}/activate').status_code == 200
    rows = client.get('/api/config/llm/models').json()['models']
    assert sum(r['is_active'] for r in rows) == 1
    assert next(r for r in rows if r['is_active'])['alias'] == 'edited'


def test_duplicate_registration_preserves_active_model(client):
    assert register(client).status_code == 200
    assert register(client).status_code == 400
    assert llm_client._resolve_registered()['model'] == 'demo-model'


def test_validation_and_missing_model(client):
    assert client.post('/api/config/llm/models', json={
        'alias': 'bad', 'provider': 'vllm', 'model_identifier': 'demo',
        'api_base': 'https://user:password@example.com/v1',
    }).status_code == 400
    assert client.post('/api/config/llm/models', json={
        'alias': 'bad', 'provider': 'vllm', 'model_identifier': 'demo',
        'api_base': 'http://[invalid',
    }).status_code == 400
    assert client.post('/api/config/llm/models/999/activate').status_code == 404
    assert client.post('/api/config/llm/models/999/test').status_code == 404


def test_probe_does_not_leak_secrets_or_change_selection(client, monkeypatch):
    register(client)
    model_id = client.get('/api/config/llm/models').json()['models'][0]['id']
    monkeypatch.setattr(llm_client, 'probe', lambda *args: (False, 'secret-key-1234'))
    result = client.post(f'/api/config/llm/models/{model_id}/test').json()
    assert not result['ok'] and 'secret' not in result['message']
    assert llm_client._resolve_registered()['model'] == 'demo-model'


if __name__ == '__main__':
    assert callable(register)
