"""Offline build acceptance against an isolated ops DB; no external LLM calls."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
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


def main():
    assert (ROOT / '03_frontend/dist/index.html').is_file(), 'Build the frontend first'
    previous = db.get_db_path
    worker_chat, narrative_chat = workers.chat, narrative.chat
    try:
        with tempfile.TemporaryDirectory() as folder:
            db.get_db_path = lambda: str(Path(folder) / 'smoke.db')
            db.init_db()
            workers.chat = narrative.chat = offline
            run_test_bench('PACK-ATLAS-01')
            score_program('PACK-ATLAS-01')
            with TestClient(app) as client:
                assert client.get('/api/health').json()['status'] == 'ok'
                risk = client.get('/api/programs/PACK-ATLAS-01/risk').json()
                assert any(r['risk_band'] == 'HIGH' and 'thermal' in r['entity_id'] for r in risk['scores'])
                hits = client.get('/api/kb/search', params={'q': 'thermal'}).json()
                assert hits
                for hit in hits:
                    assert client.get('/api/asset/' + hit['asset_id']).content
                response = client.get('/api/review/PACK-ATLAS-01/stream?review_id=REV-DEPLOY-SMOKE')
                import json
                events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
                assert events[-1]['type'] == 'done'
                assert sum(e['type'] == 'worker_done' for e in events) == 5
                assert [e['value'] for e in events if e['type'] == 'recommendation'] == ['CONDITIONAL']
    finally:
        db.get_db_path = previous
        workers.chat, narrative.chat = worker_chat, narrative_chat
    print('NPI smoke OK: HIGH risk, assets, 5 workers, CONDITIONAL, done')


if __name__ == '__main__':
    assert ROOT.is_dir()
    main()
