"""Review score provenance and decision-grounded narratives."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import pytest
from common import db, source
from common.config import get_config
from common.evidence import get_evidence
from engineering.test_bench import run_test_bench
from knowledge import kb
from ml.train import train
from ml.risk_model import score_program
from agents import workers, narrative
from agents.supervisor import run_gate_review

KEYS=['PACK-ATLAS-01','PACK-ATLAS-01@atlas-v2','PACK-ATLAS-01@atlas-v3']


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'get_db_path',lambda:str(tmp_path/'ops.db'))
    monkeypatch.setitem(get_config()['ml'],'model_dir',str(tmp_path/'models'))
    monkeypatch.setitem(get_config()['data'],'kb_dir',str(tmp_path/'kb'))
    def offline(*a,**k):raise RuntimeError('offline')
    monkeypatch.setattr(workers,'chat',offline)
    monkeypatch.setattr(narrative,'chat',offline)
    db.init_db()
    for key in ['PACK-ORION-00','PACK-VEGA-00']+KEYS:run_test_bench(key)
    train()
    for key in KEYS:score_program(key)
    kb.build_kb()


@pytest.mark.parametrize('key,outcome',zip(KEYS,['CONDITIONAL','CONDITIONAL','PASS']))
def test_scores_survive_sse_and_persistence_and_match_evidence(prepared,key,outcome):
    events=list(run_gate_review('report-'+key,key))
    assert next(e['value'] for e in events if e['type']=='recommendation')==outcome
    assessments={e['worker']:e['assessment'] for e in events if e['type']=='worker_done' and 'assessment' in e}
    risk=assessments['designrisk']
    original=json.loads(get_evidence(risk['evidence_ids'][0])['payload_json'])
    chosen=next(s for s in original if s['entity_id']==risk['entity_id'])
    assert risk['score']==chosen['risk_prob']
    assert risk['calibration']=='not_validated'
    retrieval=assessments['knowledgereuse']
    original=json.loads(get_evidence(retrieval['evidence_ids'][0])['payload_json'])
    assert [(h['asset_id'],h['score']) for h in retrieval['hits']]==[(h['asset_id'],h['score']) for h in original]
    for hit in retrieval['hits']:
        assert 0<=hit['score']<=1.000001
        assert hit['score']==pytest.approx(.7*hit['lexical_score']+.3*hit['vector_score'])
    with db.get_connection() as conn:
        row=conn.execute('SELECT worker_results,narrative FROM gate_reviews WHERE review_id=?',('report-'+key,)).fetchone()
    saved=json.loads(row['worker_results'])
    assert {w['worker']:w['assessment'] for w in saved if 'assessment' in w}==assessments
    assert 'Why this result' in row['narrative'] and 'Next action' in row['narrative']
    assert 'not measure confidence in accuracy' in row['narrative']
    if key==KEYS[1]:
        assert '24 of 30' in row['narrative'] and '1 MARGINAL' in row['narrative']
        assert 'Thermal engineering' in row['narrative']
    if outcome=='PASS':
        assert 'checks are satisfied' in row['narrative']
        assert 'Resolve the flagged' not in row['narrative']


def test_no_match_and_no_score_do_not_invent_confidence(prepared,monkeypatch):
    with db.get_connection() as conn:
        conn.execute("INSERT INTO gate_reviews(review_id,program_id) VALUES('empty','PACK-ATLAS-01')")
    monkeypatch.setattr(kb,'search',lambda *a,**kw:[])
    monkeypatch.setitem(workers.TOOLS,'get_design_risk',lambda *a:[])
    risk=workers.run_designrisk_worker('empty',KEYS[0])
    retrieved=workers.run_knowledgereuse_worker('empty',KEYS[0])
    assert risk['assessment']['score'] is None and risk['assessment']['risk_band'] is None
    assert 'no current requirement scores' in risk['findings']
    assert retrieved['assessment']['hits']==[]
    text=narrative.review_summary(KEYS[0],[risk,retrieved],'CONDITIONAL',{'coverage':{'traced':4,'total':5,'pct':.8,'gaps':['cost']},'results':[],'missing_standards':[],'issues':[]})
    assert 'unavailable' in text and 'No supporting retrieval matches' in text


def test_fail_summary_names_failure_and_blocks_invalid_model_prefix(monkeypatch):
    context={'coverage':{'traced':2,'total':5,'pct':.4,'gaps':['A','B','C']},'results':[{'test_id':'TEST-X','verdict':'FAIL'}],'missing_standards':['UN38.3'],'issues':[]}
    monkeypatch.setattr(narrative,'chat',lambda *a,**kw:'Gate review for P: recommendation PASS. Fabricated 999 volts.')
    text=''.join(narrative.narrate('P',[],'FAIL',context=context))
    assert 'recommendation FAIL' in text and '1 FAIL' in text
    assert 'TEST-X' in text and 'UN38.3' in text
    assert '999' not in text and 'recommendation PASS' not in text


if __name__=='__main__':
    assert len(KEYS)==3
