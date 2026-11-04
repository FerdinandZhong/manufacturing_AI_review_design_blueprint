"""Revision agreement and evidence isolation across all consumers."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi.testclient import TestClient
from common import source, db
from common.config import get_config
from data_generation.generate_snapshots import build_snapshots
from engineering.test_bench import run_test_bench, _verdict
from engineering.metrics import summary
from engineering.traceability import build_matrix
from ml.train import train, build_features
from ml.risk_model import score_program
from knowledge.asset_registry import generated_reports
from knowledge import semantic
from api.main import app

KEYS = ['PACK-ATLAS-01','PACK-ATLAS-01@atlas-v2','PACK-ATLAS-01@atlas-v3']

@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.setattr(db,'get_db_path',lambda:str(tmp_path/'ops.db'))
    monkeypatch.setitem(get_config()['ml'],'model_dir',str(tmp_path/'models'))
    db.init_db()
    for key in ['PACK-ORION-00','PACK-VEGA-00'] + KEYS:
        run_test_bench(key)
    train()
    for key in KEYS:
        score_program(key)
    return TestClient(app)

def test_revision_volume_and_independent_observations(prepared, monkeypatch):
    assert build_snapshots()==build_snapshots()
    expanded=source.get_snapshot(KEYS[1])
    assert (len(expanded['requirements']),len(expanded['bom_items']),len(expanded['test_plans']),len(expanded['observations']))==(30,48,24,192)
    before=run_test_bench(KEYS[1])
    designs=source.list_design_specs(KEYS[1])
    for d in designs:
        d['value']=9999
    monkeypatch.setattr(source,'list_design_specs',lambda _:designs)
    assert run_test_bench(KEYS[1])==before
    assert _verdict(80,100,'lower')=='PASS'
    assert _verdict(103,100,'lower')=='FAIL'

def test_cockpit_canvas_and_revision_agree(prepared):
    for key, outcome, count in zip(KEYS,['CONDITIONAL','CONDITIONAL','PASS'],[5,30,30]):
        detail=prepared.get('/api/programs/'+key).json()
        packet=semantic.context(program_id=key)['packet']
        assert detail['metrics']==packet['metrics']
        assert detail['identity']==packet['snapshot']
        assert detail['metrics']['requirement_count']==count
        assert detail['metrics']['recommendation']==outcome
        assert detail['metrics']['unscored_requirements']==0
    assert summary(KEYS[0])['coverage']['pct']==.8
    assert summary(KEYS[2])['coverage']['pct']==1.

def test_scoring_without_results_and_multiple_bom(prepared):
    with db.get_connection() as conn:
        conn.execute('DELETE FROM test_results WHERE program_id=?',(KEYS[1],))
    assert len(score_program(KEYS[1]))==30
    assert len(build_features([KEYS[1]]))==0
    features=build_features([KEYS[1]],require_labels=False)
    row=features[features.req_id=='REQ-ATLAS-range'].iloc[0]
    assert row.bom_cost==35+2*43
    assert not summary(KEYS[1])['prepared']
    assert summary(KEYS[1])['recommendation'] is None

def test_multiple_tests_preserve_worst_verdict(prepared, monkeypatch):
    plans=source.list_test_plans(KEYS[1])
    extra={**plans[0],'test_id':'T-ATLAS-extra'}
    monkeypatch.setattr(source,'list_test_plans',lambda _:[*plans,extra])
    with db.get_connection() as conn:
        conn.execute("INSERT INTO test_results(result_id,test_id,program_id,measured_value,verdict) VALUES('extra','T-ATLAS-extra',?,1,'FAIL')",(KEYS[1],))
        conn.execute("UPDATE test_results SET snapshot_id=? WHERE result_id='extra'",(source.snapshot_identity(KEYS[1])['snapshot_id'],))
    row=build_matrix(KEYS[1])['rows'][0]
    assert len(row['test_ids'])==2 and row['verdict']=='FAIL'

def test_report_records_and_snapshot_result_ids(prepared):
    result_ids=[]
    for key in KEYS:
        for report in generated_reports(key):
            content=json.loads(report['blob'])
            plan=next(p for p in source.list_test_plans(key) if p['test_id']==content['test_plan']['test_id'])
            assert content['test_plan']['standard']==plan['standard']
            assert content['snapshot_id']==source.snapshot_identity(key)['snapshot_id']
        result_ids += [r['result_id'] for r in run_test_bench(key)]
    assert len(result_ids)==len(set(result_ids))

def test_external_measurements_cannot_change_verdict(prepared, monkeypatch):
    before=summary(KEYS[1])['recommendation']
    monkeypatch.setattr(semantic,'reference_rows',lambda:[])
    assert summary(KEYS[1])['recommendation']==before

def test_review_snapshot_identity_and_reuse(prepared, monkeypatch):
    from agents import workers, narrative
    monkeypatch.setattr(workers, 'chat', lambda *a,**k: (_ for _ in ()).throw(RuntimeError('offline')))
    monkeypatch.setattr(narrative, 'chat', lambda *a,**k: (_ for _ in ()).throw(RuntimeError('offline')))
    body=prepared.post('/api/programs/'+KEYS[2]+'/reviews',json={'request_id':'snapshot-check'}).json()
    identity=source.snapshot_identity(KEYS[2])
    assert body['snapshot_id']==identity['snapshot_id']
    assert body['revision_id']=='atlas-v3' and body['canonical_program_id']=='PACK-ATLAS-01'
    assert body['recommendation']=='PASS'
    evidence=prepared.get('/api/reviews/'+body['review_id']+'/evidence').json()['evidence']
    assert evidence and all(e['data_version']==identity['snapshot_id'] for e in evidence)
    repeat=prepared.post('/api/programs/'+KEYS[2]+'/reviews',json={'request_id':'snapshot-check'}).json()
    assert repeat==body
    from agents.supervisor import run_gate_review
    with pytest.raises(ValueError,match='different program'):
        list(run_gate_review(body['review_id'],KEYS[1]))
    assert summary(KEYS[2])['latest_review']['recommendation']=='PASS'


def test_scope_filters_future_and_stale_evidence(prepared):
    from knowledge.asset_registry import scoped_assets
    future=generated_reports(KEYS[2])[0]
    current=generated_reports(KEYS[1])[0]
    stale={**current,'snapshot_id':'stale'}
    selected=scoped_assets([future,stale,current],KEYS[1])
    assert len(selected)==1 and selected[0]['snapshot_id']==current['snapshot_id']
    unknown='PACK-ATLAS-01@unknown'
    assert prepared.get('/api/semantic/context',params={'program_id':unknown}).status_code==404
    assert prepared.post('/api/semantic/explain',json={'program_id':unknown}).status_code==404
    packet=semantic.context(program_id=KEYS[1])['packet']
    direct=[link for link in packet['evidence_links'] if link['kind']=='direct_demo']
    assert len(direct)==1 and direct[0]['program_key']==KEYS[1]
    assert direct[0]['test_id']=='T-ATLAS-thermal-01'


def test_tampered_snapshot_is_rejected(tmp_path, monkeypatch):
    snapshot=build_snapshots()[1]
    snapshot['requirements'][0]['target_value']+=1
    directory=tmp_path/'data'/'raw'/'snapshots'
    directory.mkdir(parents=True)
    (directory/'atlas-v2.json').write_text(json.dumps(snapshot))
    monkeypatch.setattr(source,'CFG_PROJECT_ROOT',str(tmp_path))
    with pytest.raises(ValueError,match='checksum mismatch'):
        source.get_snapshot(KEYS[1])


if __name__ == '__main__':
    assert len(KEYS)==3
    assert _verdict(103,100)=='MARGINAL'
    print('Unified revision test contract OK')
