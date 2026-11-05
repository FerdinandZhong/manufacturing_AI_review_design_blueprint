"""Offline build acceptance against an isolated ops DB; no external LLM calls."""
import os
import sys
from pathlib import Path

if '__file__' in globals():
    ROOT = Path(__file__).resolve().parents[1]
else:
    ROOT = Path(os.environ.get('CDSW_PROJECT_HOME', os.getcwd())).resolve()
    if not (ROOT / '02_backend' / 'common' / 'config.py').is_file():
        raise RuntimeError(
            'Could not locate the Vehicle NPI project root. Run this task from '
            'the project directory or set CDSW_PROJECT_HOME to that directory.'
        )
sys.path.insert(0, str(ROOT / '02_backend'))

import tempfile
from fastapi.testclient import TestClient
from common import db
from engineering.test_bench import run_test_bench
from ml.risk_model import score_program
from agents import workers, narrative
from api.main import app


def offline(*args, **kwargs):
    raise RuntimeError('Smoke check uses offline narration')


def require_ok(response):
    """Report HTTP failures before inspecting endpoint-specific result fields."""
    if response.status_code != 200:
        try:
            detail = response.json().get('detail', 'Unexpected API error response')
        except (ValueError, AttributeError):
            detail = 'Non-JSON API error response'
        raise RuntimeError(
            f'Smoke check {response.request.url.path} returned HTTP '
            f'{response.status_code}: {str(detail)[:300]}'
        )
    return response


def require_object(response, field):
    payload = require_ok(response).json()
    if not isinstance(payload, dict) or field not in payload:
        raise RuntimeError(f'Smoke check {response.request.url.path} returned an invalid response: missing {field}')
    return payload


def main():
    from common.runtime import data_mode
    if data_mode()=='pilot':
        from common import providers
        assert providers.readiness()['state']=='ready', 'Pilot source is unready; no Demo fallback'
        print('Pilot contract smoke passed. Remote Workbench access acceptance remains pending.')
        return
    assert (ROOT / '03_frontend/dist/index.html').is_file(), 'Build the frontend first'
    from common.runtime import auth_mode
    from common.security import sign
    import secrets
    previous_secret = os.environ.get('NPI_INGRESS_SECRET')
    previous_origin = os.environ.get('NPI_PUBLIC_ORIGIN')
    if auth_mode()=='workbench':
        os.environ['NPI_INGRESS_SECRET'] = secrets.token_urlsafe(48)
        # AMP exposes optional defaults as empty strings. Use a test-owned origin
        # for this in-process fixture, then restore the exact deployment setting.
        os.environ['NPI_PUBLIC_ORIGIN'] = 'https://offline-smoke.invalid'
    def mock_identity(request):
        if auth_mode()=='workbench':
            actor, permission, kind = 'offline-smoke-fixture','RW','machine'
            path = request.url.path + ('?'+request.url.query.decode() if request.url.query else '')
            request.headers.update({'x-npi-actor':actor,'x-npi-permission':permission,'x-npi-auth-kind':kind,'x-npi-proof':sign(os.environ['NPI_INGRESS_SECRET'],actor,permission,kind,request.method,path,'')})
    previous = db.get_db_path
    worker_chat, narrative_chat = workers.chat, narrative.chat
    try:
        with tempfile.TemporaryDirectory() as folder:
            db.get_db_path = lambda: str(Path(folder) / 'smoke.db')
            db.init_db()
            workers.chat = narrative.chat = offline
            run_test_bench('PACK-ATLAS-01')
            score_program('PACK-ATLAS-01')
            with TestClient(app,client=('127.0.0.1',50000)) as client:
                client.event_hooks['request']=[mock_identity]
                assert require_object(client.get('/api/health'), 'status')['status'] == 'ok'
                risk = require_object(client.get('/api/programs/PACK-ATLAS-01/risk'), 'scores')
                assert isinstance(risk['scores'], list), 'Risk endpoint must return a scores list'
                assert any(r['risk_band'] == 'HIGH' and 'thermal' in r['entity_id'] for r in risk['scores'])
                hits = require_ok(client.get('/api/kb/search', params={'q': 'thermal'})).json()
                assert isinstance(hits,list) and hits, 'Knowledge search returned no asset list'
                for hit in hits:
                    assert require_ok(client.get('/api/asset/' + hit['asset_id'])).content
                response = require_ok(client.get('/api/review/PACK-ATLAS-01/stream?review_id=REV-DEPLOY-SMOKE'))
                import json
                events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
                assert events and events[-1]['type'] == 'done', 'Review stream did not complete'
                assert sum(e['type'] == 'worker_done' for e in events) == 5
                assert [e['value'] for e in events if e['type'] == 'recommendation'] == ['CONDITIONAL']
    finally:
        for name,value in [('NPI_INGRESS_SECRET',previous_secret),('NPI_PUBLIC_ORIGIN',previous_origin)]:
            if value is None:
                os.environ.pop(name,None)
            else:
                os.environ[name]=value
        db.get_db_path = previous
        workers.chat, narrative.chat = worker_chat, narrative_chat
    print('NPI smoke OK: HIGH risk, assets, 5 workers, CONDITIONAL, done')


if __name__ == '__main__':
    assert ROOT.is_dir()
    main()
