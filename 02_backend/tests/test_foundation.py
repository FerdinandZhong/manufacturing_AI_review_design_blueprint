"""Mocked Workbench ingress, source contracts, and strict Pilot isolation."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import copy
import importlib.util
import json
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from api.main import app
from common import db, source, providers
from common.config import get_config
from common.runtime import auth_mode, data_mode
from common.security import sign

ORIGIN='https://npi.example.com'
SECRET='test-owned-proof-secret'


def fixture_snapshot():
    common={'program_id':'PILOT-TEST','revision_id':'r1','source_id':'test-owned-import','provenance':'Explicit test fixture, not operational data'}
    return {'schema_version':'npi-pilot-v1','source_kind':'actual','source_id':common['source_id'], 'revision_id':'r1', 'extracted_at':'2026-10-23T08:00:00Z','provenance':common['provenance'],
            'program':{'program_id':'PILOT-TEST','name':'Test-owned contract program','vehicle_platform':'fixture','stage':'VALIDATION','gate_status':'PENDING'},
            'requirements':[{**common,'req_id':'Q1','text':'Test requirement','category':'thermal','target_value':10,'unit':'degC','priority':'P0','status':'APPROVED','acceptance_direction':'lower'}],
            'design_specs':[{**common,'spec_id':'D1','req_id':'Q1','value':8,'unit':'degC','parameter':'temperature_rise','version':'r1'}],
            'suppliers':[{**common,'supplier_id':'S1','name':'Fixture supplier','region':'test'}],
            'bom_items':[{**common,'part_id':'B1','spec_id':'D1','supplier_id':'S1','name':'Fixture component','qty':2,'unit_cost':10,'mass_kg':1}],
            'test_plans':[{**common,'test_id':'T1','req_id':'Q1','method':'fixture_method','unit':'degC','target_value':10,'acceptance_direction':'lower','standard':'owner protocol'}],
            'observations':[{**common,'observation_id':'O1','test_id':'T1','unit':'degC','measured_value':8.2,'recorded_at':'2026-10-22T08:00:00Z','source_native_verdict':'accepted'}]}


@pytest.fixture
def secured(monkeypatch,tmp_path):
    monkeypatch.setenv('NPI_AUTH_MODE','workbench')
    monkeypatch.setenv('NPI_INGRESS_SECRET',SECRET)
    monkeypatch.setenv('NPI_PUBLIC_ORIGIN',ORIGIN)
    monkeypatch.setenv('NPI_TRUSTED_PROXY_CIDRS','10.20.30.40/32')
    monkeypatch.setattr(db,'get_db_path',lambda:str(tmp_path/'ops.db'))
    db.init_db()
    return TestClient(app,client=('127.0.0.1',5555))


def headers(path,method='GET',permission='RW',kind='machine',actor='native-user',origin='',**extra):
    result={'x-npi-actor':actor,'x-npi-permission':permission,'x-npi-auth-kind':kind,'x-npi-proof':sign(SECRET,actor,permission,kind,method,path,origin)}
    if origin:
        result['origin']=origin
    return {**result,**extra}


def pilot(monkeypatch,tmp_path,snapshot=None):
    path=tmp_path/'source.json'
    path.write_text(json.dumps(snapshot or fixture_snapshot()))
    monkeypatch.setenv('NPI_DATA_MODE','pilot')
    monkeypatch.setenv('NPI_SOURCE_PROVIDER','canonical_import')
    monkeypatch.setenv('NPI_PILOT_SOURCE',str(path))
    return path


def test_workbench_and_pilot_defaults_fail_closed(monkeypatch):
    monkeypatch.delenv('NPI_AUTH_MODE',raising=False)
    monkeypatch.setenv('CDSW_DOMAIN','workbench.example')
    assert auth_mode()=='workbench'
    monkeypatch.setenv('NPI_AUTH_MODE','local_demo')
    with pytest.raises(RuntimeError): auth_mode()
    monkeypatch.delenv('CDSW_DOMAIN')
    monkeypatch.setenv('NPI_DATA_MODE','pilot')
    with pytest.raises(RuntimeError): auth_mode()
    monkeypatch.delenv('NPI_AUTH_MODE')
    assert auth_mode()=='workbench'


def test_direct_native_headers_and_missing_config_rejected(secured,monkeypatch):
    assert secured.get('/api/programs',headers={'REMOTE-USER':'attacker','REMOTE-USER-PERM':'RW'}).status_code==403
    assert secured.get('/api/programs',headers=headers('/api/programs',actor='forged',**{'x-npi-proof':'bad'})).status_code==403
    monkeypatch.delenv('NPI_INGRESS_SECRET')
    assert secured.get('/api/programs',headers=headers('/api/programs')).status_code==403
    assert secured.get('/api/health').status_code==200


def test_ro_reads_and_readonly_narration(secured):
    assert secured.get('/api/programs',headers=headers('/api/programs',permission='RO')).status_code==200
    # Invalid question reaches request validation, rather than a role denial.
    path='/api/semantic/explain'
    assert secured.post(path,json={'question_id':'unknown'},headers=headers(path,'POST','RO')).status_code==422


@pytest.mark.parametrize('method,path', [('POST','/api/programs/PACK-ATLAS-01/testbench'),('POST','/api/programs/PACK-ATLAS-01/reviews'),('GET','/api/review/PACK-ATLAS-01/stream?review_id=x'),('POST','/api/review/x/decision'),('POST','/api/config/llm/models'),('PUT','/api/config/llm/models/1'),('POST','/api/config/llm/models/1/activate'),('POST','/api/config/llm/models/1/test')])
def test_every_mutation_requires_rw(secured,method,path):
    response=secured.request(method,path,json={},headers=headers(path,method,'RO'))
    assert response.status_code==403
    with db.get_connection() as conn:
        event=dict(conn.execute('SELECT * FROM audit_events ORDER BY event_id DESC LIMIT 1').fetchone())
    assert event['actor']=='native-user' and event['outcome']=='authorization_denied'


@pytest.mark.parametrize('kind',['browser','machine'])
def test_cross_origin_cannot_bypass_with_bearer(secured,kind):
    path='/api/config/llm/models'
    h=headers(path,'POST',kind=kind,origin='https://evil.example',authorization='Bearer caller-supplied')
    assert secured.post(path,json={},headers=h).status_code==403


def test_browser_and_machine_csrf(secured):
    path='/api/config/llm/models'
    assert secured.post(path,json={},headers=headers(path,'POST',kind='browser')).status_code==403
    assert secured.post(path,json={},headers=headers(path,'POST',kind='browser',origin=ORIGIN)).status_code==422
    assert secured.post(path,json={},headers=headers(path,'POST',kind='machine')).status_code==422
    stream='/api/review/x/stream?review_id=x'
    assert secured.get(stream,headers=headers(stream,kind='browser')).status_code==403


def test_native_actor_overrides_typed_adjudicator(secured):
    with db.get_connection() as conn:
        conn.execute("INSERT INTO gate_reviews(review_id,program_id) VALUES('auth-test','P')")
    path='/api/review/auth-test/decision'
    r=secured.post(path,json={'decision':'REJECTED','adjudicator':'typed-impostor'},headers=headers(path,'POST',actor='actual-native-actor'))
    assert r.status_code==200 and r.json()['decided_by']=='actual-native-actor'
    with db.get_connection() as conn:
        row=dict(conn.execute('SELECT * FROM audit_events ORDER BY event_id DESC LIMIT 1').fetchone())
        annotation=dict(conn.execute('SELECT * FROM annotations').fetchone())
    assert row['actor']==annotation['adjudicator']=='actual-native-actor'
    assert 'Bearer' not in json.dumps(row)


def test_proxy_replaces_internal_identity_and_strips_credentials(secured,monkeypatch,caplog):
    root=Path(__file__).parents[2]
    spec=importlib.util.spec_from_file_location('foundation_frontend',root/'03_frontend/start_frontend.py')
    frontend=importlib.util.module_from_spec(spec);spec.loader.exec_module(frontend)
    frontend._ingress_secret=SECRET
    frontend._backend_proc=type('Alive',(),{'poll':lambda self:None})()
    seen=[]
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{"ok":true}'
    async def backend(request):
        seen.append(request)
        return httpx.Response(200,stream=Body())
    proxy=frontend.create_app(7100)
    proxy.state.backend=httpx.AsyncClient(transport=httpx.MockTransport(backend),base_url='http://127.0.0.1:7100')
    client=TestClient(proxy,client=('10.20.30.40',5000))
    raw={'REMOTE-USER':'native','REMOTE-USER-PERM':'RO','x-npi-actor':'forged','x-npi-proof':'forged','Authorization':'Bearer secret','Cookie':'secret','X-Forwarded-For':'trusted-forgery'}
    assert client.get('/api/programs',headers=raw).status_code==200
    sent=seen[0]
    assert sent.headers['x-npi-actor']=='native' and sent.headers['x-npi-permission']=='RO'
    assert all(k not in sent.headers for k in ('authorization','cookie','remote-user','remote-user-perm','x-forwarded-for'))
    assert sent.headers['x-npi-proof']==sign(SECRET,'native','RO','machine','GET','/api/programs','')
    untrusted=TestClient(proxy,client=('10.20.30.41',5000))
    assert untrusted.get('/api/programs',headers=raw).status_code==403
    assert client.get('/api/programs',headers=[('remote-user','a'),('remote-user','b'),('remote-user-perm','RW')]).status_code==403
    assert client.get('/api/programs',headers={**raw,'remote_user':'underscore'}).status_code==403
    monkeypatch.delenv('NPI_TRUSTED_PROXY_CIDRS')
    response=client.get('/api/programs',headers=raw)
    assert response.status_code==403
    assert 'NPI_TRUSTED_PROXY_CIDRS' in response.json()['detail']
    monkeypatch.setenv('NPI_PUBLIC_ORIGIN','')
    monkeypatch.delenv('CDSW_DOMAIN', raising=False)
    response=client.get('/api/runtime/status',headers=raw)
    assert response.status_code==403
    assert 'NPI_PUBLIC_ORIGIN' in response.json()['detail']
    assert 'peer=10.20.30.40' in caplog.text
    assert 'Bearer secret' not in caplog.text and 'trusted-forgery' not in caplog.text


@pytest.mark.parametrize('configured', [None, ''])
def test_workbench_defaults_end_to_end(secured, monkeypatch, configured):
    """An AMP with no user-supplied ingress settings serves authenticated APIs."""
    for name in ('NPI_PUBLIC_ORIGIN', 'NPI_TRUSTED_PROXY_CIDRS'):
        if configured is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, configured)
    monkeypatch.setenv('CDSW_DOMAIN', 'workbench.example.com')
    monkeypatch.delenv('NPI_APP_SUBDOMAIN', raising=False)
    from common.security import public_origin, forwarded_identity
    from starlette.requests import Request
    origin = 'https://vehicle-npi-platform.workbench.example.com'
    assert public_origin() == origin

    def through_frontend(path, method='GET', peer='127.0.0.1', browser_origin=origin, permission='RW'):
        request = Request({'type':'http', 'method':method, 'path':path, 'query_string':b'',
                           'client':(peer, 5000), 'server':('127.0.0.1', 8100), 'scheme':'http',
                           'headers':[(b'remote-user', b'workbench-user'),
                                      (b'remote-user-perm', permission.encode()),
                                      (b'origin', browser_origin.encode())]})
        identity = forwarded_identity(request, SECRET)
        return secured.request(method, path, json={} if method == 'POST' else None,
                               headers={**identity, 'origin':browser_origin})

    response = through_frontend('/api/runtime/status')
    assert response.status_code == 200
    assert response.json()['identity']['actor'] == 'workbench-user'
    # An authorized mutation reaches schema validation; foreign origins and RO do not.
    assert through_frontend('/api/config/llm/models', 'POST').status_code == 422
    assert through_frontend('/api/config/llm/models', 'POST', browser_origin='https://evil.example').status_code == 403
    assert through_frontend('/api/config/llm/models', 'POST', permission='RO').status_code == 403
    with pytest.raises(PermissionError, match='Untrusted Workbench ingress'):
        through_frontend('/api/runtime/status', peer='10.20.30.40')


def test_origin_discovery_and_overrides(monkeypatch):
    from common.security import public_origin, proxy_is_trusted
    monkeypatch.setenv('NPI_PUBLIC_ORIGIN', '')
    monkeypatch.setenv('CDSW_DOMAIN', 'workbench.example.com')
    monkeypatch.setenv('NPI_APP_SUBDOMAIN', 'renamed-app')
    assert public_origin() == 'https://renamed-app.workbench.example.com'
    monkeypatch.setenv('CDSW_DOMAIN', 'evil.example/path')
    with pytest.raises(ValueError):
        public_origin()
    monkeypatch.setenv('NPI_PUBLIC_ORIGIN', 'https://custom.example')
    assert public_origin() == 'https://custom.example'
    monkeypatch.setenv('NPI_PUBLIC_ORIGIN', 'http://custom.example')
    with pytest.raises(ValueError):
        public_origin()
    monkeypatch.setenv('NPI_TRUSTED_PROXY_CIDRS', '')
    assert proxy_is_trusted('127.0.0.1') and proxy_is_trusted('::1')
    assert not proxy_is_trusted('10.1.2.3')
    monkeypatch.setenv('NPI_TRUSTED_PROXY_CIDRS', '10.1.2.3/32')
    assert proxy_is_trusted('10.1.2.3') and not proxy_is_trusted('127.0.0.1')


def test_pilot_readonly_import_and_unavailable_capabilities(secured,monkeypatch,tmp_path):
    path=pilot(monkeypatch,tmp_path)
    before=path.read_bytes()
    assert source.list_programs()[0]['program_id']=='PILOT-TEST'
    assert source.list_scenarios()==[] and source.get_program('PACK-ATLAS-01') is None
    status=secured.get('/api/runtime/status',headers=headers('/api/runtime/status')).json()
    assert status['source_ready'] and not status['review_ready'] and status['mode']=='pilot'
    assert status['source']['freshness']=='not_checked'
    p='/api/programs/PILOT-TEST/data/observations'
    r=secured.get(p,headers=headers(p)).json()
    assert r['items'][0]['source_native_verdict']=='accepted'
    assert 'pilot' in r['provenance']
    p='/api/programs/PILOT-TEST/risk'
    assert secured.get(p,headers=headers(p)).json()['scores']==[]
    for method,p in [('POST','/api/programs/PILOT-TEST/testbench'),('POST','/api/programs/PILOT-TEST/reviews'),('GET','/api/kb/search?q=thermal'),('POST','/api/semantic/explain'),('GET','/api/nifi/snapshot?mode=sample')]:
        assert secured.request(method,p,json={},headers=headers(p,method)).status_code==503
    assert path.read_bytes()==before


def test_pilot_never_generates_or_uses_demo_model(monkeypatch,tmp_path):
    pilot(monkeypatch,tmp_path)
    from data_generation.generate_synthetic_data import generate
    from data_generation.generate_snapshots import generate as snapshots
    from engineering.test_bench import run_test_bench
    from ml.train import train
    from ml.risk_model import score_program, get_scores, explain
    from knowledge.kb import build_kb
    for fn,args in [(generate,(str(tmp_path/'bad'),)),(snapshots,(str(tmp_path/'bad'),)),(run_test_bench,('PILOT-TEST',)),(train,()),(score_program,('PILOT-TEST',)),(build_kb,())]:
        with pytest.raises(RuntimeError,match='disabled in Pilot'): fn(*args)
    assert not (tmp_path/'bad').exists()
    assert get_scores('PILOT-TEST')==[] and explain()==[]
    from scripts.prepare import main
    original=copy.deepcopy(fixture_snapshot())
    main()
    assert providers.load()['requirements']==original['requirements']


@pytest.mark.parametrize('mutation',[
    lambda s:s.update(source_kind='synthetic'),
    lambda s:s['requirements'].append(copy.deepcopy(s['requirements'][0])),
    lambda s:s['requirements'][0].update(unit='unknown'),
    lambda s:s['design_specs'][0].update(req_id='missing'),
    lambda s:s['test_plans'][0].update(revision_id='wrong'),
    lambda s:s['observations'][0].update(unit='V'),
    lambda s:s['observations'][0].update(recorded_at=123),
    lambda s:s['requirements'][0].update(provenance=''),
    lambda s:s['bom_items'][0].update(supplier_id='missing'),
])
def test_invalid_source_is_unready_without_demo(secured,monkeypatch,tmp_path,mutation):
    snapshot=fixture_snapshot();mutation(snapshot);pilot(monkeypatch,tmp_path,snapshot)
    assert providers.readiness()['state']=='unready'
    with pytest.raises(providers.SourceUnavailable): source.list_programs()
    assert secured.get('/api/programs',headers=headers('/api/programs')).status_code==503


def test_missing_pilot_provider_does_not_resolve_csv(secured,monkeypatch):
    monkeypatch.setenv('NPI_DATA_MODE','pilot')
    monkeypatch.setenv('NPI_SOURCE_PROVIDER','unconfigured')
    assert providers.readiness()['state']=='unready'
    assert secured.get('/api/programs',headers=headers('/api/programs')).status_code==503


def test_real_frontend_hop_reaches_backend_authorization(secured,monkeypatch):
    root=Path(__file__).parents[2]
    spec=importlib.util.spec_from_file_location('foundation_e2e_proxy',root/'03_frontend/start_frontend.py')
    frontend=importlib.util.module_from_spec(spec);spec.loader.exec_module(frontend)
    frontend._ingress_secret=SECRET
    frontend._backend_proc=type('Alive',(),{'poll':lambda self:None})()
    proxy=frontend.create_app(7100)
    proxy.state.backend=httpx.AsyncClient(transport=httpx.ASGITransport(app=app,client=('127.0.0.1',5555)),base_url='http://127.0.0.1:7100')
    client=TestClient(proxy,client=('10.20.30.40',5000))
    path='/api/config/llm/models'
    native={'remote-user':'upstream-native','remote-user-perm':'RW','origin':ORIGIN}
    # Reaching body validation proves the real backend accepted this identity and Origin.
    assert client.post(path,json={},headers=native).status_code==422
    assert client.post(path,json={},headers={**native,'remote-user-perm':'RO'}).status_code==403
    assert client.post(path,json={},headers={**native,'origin':'https://evil.example','authorization':'Bearer forged'}).status_code==403
    monkeypatch.setenv('NPI_AUTH_MODE','local_demo')
    monkeypatch.setenv('NPI_LOCAL_ORIGIN','http://127.0.0.1:8199')
    assert client.post(path,json={},headers={'origin':'http://127.0.0.1:8199'}).status_code==422
    assert client.post(path,json={},headers={'origin':'https://evil.example'}).status_code==403


def test_pilot_storage_cannot_share_demo_database(monkeypatch):
    from common.config import get_db_path
    monkeypatch.setenv('NPI_DATA_MODE','pilot')
    cfg=get_config()
    monkeypatch.setitem(cfg,'pilot',{'ops_db_path':cfg['data']['db_path']})
    with pytest.raises(RuntimeError,match='must differ'):
        get_db_path()


def test_readiness_does_not_invent_prepared_reviews(secured):
    response=secured.get('/api/runtime/status',headers=headers('/api/runtime/status')).json()
    assert not response['review_ready']


@pytest.mark.parametrize('configured_origin',[None, '', 'https://configured-workbench.invalid'])
def test_offline_smoke_uses_mocked_workbench_hop(secured,monkeypatch,configured_origin):
    monkeypatch.setenv('CDSW_DOMAIN','test-workbench.invalid')
    monkeypatch.delenv('NPI_AUTH_MODE',raising=False)
    monkeypatch.delenv('NPI_PUBLIC_ORIGIN',raising=False)
    if configured_origin is not None:
        monkeypatch.setenv('NPI_PUBLIC_ORIGIN',configured_origin)
    monkeypatch.delenv('NPI_INGRESS_SECRET',raising=False)
    from engineering.test_bench import run_test_bench
    from ml.train import train
    from knowledge.kb import build_kb
    for pid in ('PACK-ORION-00','PACK-VEGA-00'):
        run_test_bench(pid)
    train()
    build_kb()
    root=Path(__file__).parents[2]
    spec=importlib.util.spec_from_file_location('foundation_smoke',root/'cai_integration/smoke_test.py')
    smoke=importlib.util.module_from_spec(spec);spec.loader.exec_module(smoke)
    smoke.main()
    assert 'NPI_INGRESS_SECRET' not in os.environ
    assert os.environ.get('NPI_PUBLIC_ORIGIN') == configured_origin
    assert auth_mode()=='workbench'


def test_smoke_http_failures_report_status_and_detail():
    root=Path(__file__).parents[2]
    spec=importlib.util.spec_from_file_location('diagnostic_smoke',root/'cai_integration/smoke_test.py')
    smoke=importlib.util.module_from_spec(spec);spec.loader.exec_module(smoke)
    request=httpx.Request('GET','http://testserver/api/programs/PACK-ATLAS-01/risk')
    denied=httpx.Response(403,json={'detail':'Invalid trusted frontend proof'},request=request)
    with pytest.raises(RuntimeError,match='HTTP 403: Invalid trusted frontend proof'):
        smoke.require_object(denied,'scores')
    invalid=httpx.Response(200,json={'unexpected':[]},request=request)
    with pytest.raises(RuntimeError,match='missing scores'):
        smoke.require_object(invalid,'scores')


def test_pilot_metrics_ignore_demo_policies_and_operational_rows(secured,monkeypatch,tmp_path):
    pilot(monkeypatch,tmp_path)
    identity=source.snapshot_identity('PILOT-TEST')
    with db.get_connection() as conn:
        conn.execute("INSERT INTO test_results(result_id,test_id,program_id,measured_value,verdict,snapshot_id) VALUES('fake-result','T1','PILOT-TEST',8,'PASS',?)",(identity['snapshot_id'],))
        conn.execute("INSERT INTO design_risk_scores(program_id,entity_type,entity_id,risk_band,risk_prob,snapshot_id) VALUES('PILOT-TEST','requirement','Q1','HIGH',.99,?)",(identity['snapshot_id'],))
        conn.execute("INSERT INTO gate_reviews(review_id,program_id,recommendation,decision,state,snapshot_id) VALUES('fake-review','PILOT-TEST','PASS','APPROVED','RELEASED',?)",(identity['snapshot_id'],))
    import engineering.metrics as metrics
    import engineering.traceability as traceability
    def forbidden(*args,**kwargs):
        raise AssertionError('Pilot inspection must not read operational decisions or apply demo policies')
    monkeypatch.setattr(metrics,'get_connection',forbidden)
    monkeypatch.setattr(metrics,'decide',forbidden)
    monkeypatch.setattr(metrics,'missing_standards',forbidden)
    monkeypatch.setattr(metrics,'get_scores',forbidden)
    monkeypatch.setattr(traceability,'get_connection',forbidden)
    for suffix in ('','/snapshot'):
        path='/api/programs/PILOT-TEST'+suffix
        response=secured.get(path,headers=headers(path))
        assert response.status_code==200
        m=response.json()['metrics']
        assert m['metric_status']=='structural_source_inspection_only'
        assert m['requirement_count']==m['design_count']==m['planned_test_count']==m['observation_count']==1
        assert m['bom_cost']==20 and m['bom_mass_kg']==2
        assert m['coverage']['pct']==1 and m['coverage_status']=='structural_only'
        for key in ('high_risk_requirements','tests_needing_attention','test_count','unscored_requirements','missing_standards','recommendation','latest_review','executed_coverage','open_issues','action_completion'):
            assert m[key] is None
        assert not m['prepared'] and not m['review_ready']
        assert 'acceptance_margin' not in m['definitions']
        assert 'seeded' not in m['observation_evidence_coverage']['basis']
        assert m['unsupported_metrics']['standards_coverage']=='unavailable_pending_approved_pilot_rules'
    path='/api/programs/PILOT-TEST/matrix'
    matrix=secured.get(path,headers=headers(path)).json()
    assert matrix['status']=='structural_only'
    assert matrix['verdict_status']=='unavailable_pending_approved_pilot_rules'
    assert matrix['rows'][0]['verdict'] is None
    assert matrix['rows'][0]['spec_ids']==['D1'] and matrix['rows'][0]['test_ids']==['T1']


def test_pilot_preparation_wrapper_never_runs_release_test_suites(monkeypatch):
    monkeypatch.setenv('NPI_DATA_MODE','pilot')
    root=Path(__file__).parents[2]
    spec=importlib.util.spec_from_file_location('foundation_prepare_wrapper',root/'cai_integration/prepare_application.py')
    wrapper=importlib.util.module_from_spec(spec);spec.loader.exec_module(wrapper)
    calls=[]
    monkeypatch.setattr(wrapper.subprocess,'run',lambda command,**kwargs:calls.append(command))
    from data_generation import generate_synthetic_data
    def forbidden(*args,**kwargs):
        raise AssertionError('Pilot wrapper must not generate sources')
    monkeypatch.setattr(generate_synthetic_data,'generate',forbidden)
    wrapper.main()
    assert len(calls)==4
    assert all('pytest' not in command for command in calls)
    assert all('generate_synthetic_data.py' not in ' '.join(command) for command in calls)
    assert any('prepare.py' in ' '.join(command) for command in calls)
    assert any('smoke_test.py' in ' '.join(command) for command in calls)


if __name__=='__main__':
    assert fixture_snapshot()['source_kind']=='actual'
    assert len(fixture_snapshot()['observations'])==1
    print('Foundation test fixtures OK')
