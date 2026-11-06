"""Language changes preserve engineering facts and authorization boundaries."""
import asyncio
import hashlib
import json
import re
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from common.i18n import translate_text, localize_payload, normalize_query, nifi_intent, semantic_intent
from common.localization import LocalizationMiddleware
from common import nifi
from common.security import is_mutation


def test_report_preserves_measurements_identifiers_and_canonical_result():
    source = {'recommendation':'CONDITIONAL','score':.995,'test_id':'T-ATLAS-thermal-01',
              'narrative':'Gate review for PACK-ATLAS-01: recommendation CONDITIONAL.\nThe highest-scored requirement is REQ-ATLAS-thermal, with a 99.5% predicted risk score (HIGH).'}
    result = localize_payload(source,'zh')
    assert result['recommendation'] == source['recommendation']
    assert result['score'] == source['score'] and result['test_id'] == source['test_id']
    assert '有条件通过' in result['narrative'] and '99.5%' in result['narrative']
    assert 'REQ-ATLAS-thermal' in result['narrative']
    assert result['_source_texts']['narrative'] == source['narrative']
    assert localize_payload(source,'en') == source


def test_localized_answer_digest_and_source_digest():
    result=localize_payload({'answer':'No model was called.','answer_sha256':'old','source_sha256':'a'*64},'zh')
    assert result['answer_sha256']==hashlib.sha256(result['answer'].encode()).hexdigest()
    assert result['source_sha256']=='a'*64


@pytest.mark.parametrize('question,intent', [('当前管道运行状态如何？','status'),('哪些处理器无效或已停止？','health'),('显示管道拓扑','topology'),('显示近期公告','bulletins')])
def test_chinese_nifi_question_uses_same_read_only_snapshot(question,intent):
    app=FastAPI(); app.include_router(nifi.router); app.add_middleware(LocalizationMiddleware)
    client=TestClient(app)
    response=client.post('/api/nifi/ask',json={'question':question,'mode':'sample'})
    assert response.status_code==200 and response.headers['content-language']=='zh-CN'
    data=response.json()
    assert data['intent']==intent
    assert data['snapshot']['metrics']==nifi.sample_snapshot()['metrics']
    assert data['snapshot']['name']=='电池测试证据摄取'
    assert not is_mutation('POST','/api/nifi/ask')


@pytest.mark.parametrize('question',['请停止处理器','帮我启动管道','重启管道','删除连接','显示昨天的公告','Show historical logs'])
def test_nifi_rejects_mutation_and_history(question):
    with pytest.raises(ValueError):nifi_intent(question)


def test_chinese_domain_queries():
    assert normalize_query('请查找热隔离证据')=='thermal containment evidence'
    assert semantic_intent('电池包布局是什么？')=='packaging'
    assert semantic_intent('外部证据是否适用？')=='applicability'
    assert semantic_intent('热风险有哪些？')=='thermal'


def test_stream_localizes_split_utf8_and_keeps_protocol_fields():
    async def run():
        payload={'type':'token','text':'Gate review for PACK-ATLAS-01: recommendation CONDITIONAL.'}
        raw=('data: '+json.dumps(payload)+'\n\n'+'data: '+json.dumps({'type':'recommendation','value':'CONDITIONAL'})+'\n\n').encode()
        async def app(scope,receive,send):
            await send({'type':'http.response.start','status':200,'headers':[(b'content-type',b'text/event-stream')]})
            for chunk in [raw[:5],raw[5:81],raw[81:]]:
                await send({'type':'http.response.body','body':chunk,'more_body':True})
            await send({'type':'http.response.body','body':b'','more_body':False})
        sent=[]
        async def send(message):sent.append(message)
        await LocalizationMiddleware(app)({'type':'http','headers':[(b'accept-language',b'zh-CN')],'query_string':b''},None,send)
        body=b''.join(m.get('body',b'') for m in sent).decode()
        events=[json.loads(line[6:]) for line in body.splitlines() if line.startswith('data: ')]
        assert '有条件通过' in events[0]['text']
        assert events[0]['_source_texts']['text']==payload['text']
        assert events[1]=={'type':'recommendation','value':'CONDITIONAL'}
    asyncio.run(run())


def test_api_chinese_queries_and_output_preserve_evidence(monkeypatch):
    from common import db
    from engineering.test_bench import run_test_bench
    from ml.train import train
    from ml.risk_model import score_program
    from knowledge import kb
    from api.main import app
    db.init_db()
    for pid in ['PACK-ATLAS-01','PACK-ORION-00','PACK-VEGA-00']:run_test_bench(pid)
    train();score_program('PACK-ATLAS-01');kb.build_kb()
    client=TestClient(app)
    en=client.get('/api/kb/search',params={'q':'thermal containment','k':5}).json()
    response=client.get('/api/kb/search',params={'q':'热隔离','k':5})
    assert response.headers['content-language']=='zh-CN'
    zh=response.json()
    assert [(h['asset_id'],h['score']) for h in zh]==[(h['asset_id'],h['score']) for h in en]
    for english,chinese in zip(en,zh):
        assert chinese['title']==translate_text(english['title'])
    for question,intent in [('热风险是什么？','thermal'),('电池封装布局','packaging'),('如何泄压？','venting'),('外部证据是否适用？','applicability')]:
        english=client.post('/api/semantic/explain',json={'question_id':intent}).json()
        response=client.post('/api/semantic/explain',json={'question':question})
        assert response.status_code==200 and response.headers['content-language']=='zh-CN'
        chinese=response.json()
        assert chinese['answer']==translate_text(english['answer'])
        assert [f['value'] for f in chinese['packet']['facts']]==[f['value'] for f in english['packet']['facts']]
        assert chinese['answer']!=english['answer']
    # The caller can explicitly choose English for a Chinese question.
    response=client.post('/api/semantic/explain',json={'question':'热风险是什么？'},headers={'Accept-Language':'en'})
    assert response.headers['content-language']=='en'
    assert 'Atlas has' in response.json()['answer']


def test_language_switch_can_restore_translated_arrays():
    payload={'constraints':['No model was called.'],'value':'HIGH','id':'unicode-word-lower-v1'}
    translated=localize_payload(payload,'zh')
    assert translated['constraints']==['未调用模型。']
    assert translated['_source_texts']['constraints']==payload['constraints']
    assert translated['id']==payload['id']


@pytest.mark.parametrize('claim',[
    'The Atlas program records a MARGINAL thermal test result [F-TEST].',
    'Atlas has a HIGH thermal design-risk rating [F-RISK].',
    'The Atlas program requires a thermal requirement at 10 degC [F-REQ].',
    'The published study provides 11 experiments [F-REF].'])
def test_all_accepted_model_claim_forms_have_chinese_output(claim):
    translated=translate_text(claim)
    assert 'Atlas' not in translated and 'study' not in translated
    assert re.findall(r'\[F-[A-Z]+\]',translated)==re.findall(r'\[F-[A-Z]+\]',claim)


def test_compound_summary_is_translated_before_short_claims():
    sentence='Atlas has a MARGINAL thermal bench result [F-TEST] and a HIGH design-risk band [F-RISK].'
    assert translate_text(sentence)=='阿特拉斯的热台架结果为临界 [F-TEST]，设计风险等级为高 [F-RISK]。'


if __name__=='__main__':
    assert translate_text('Ready') != 'Ready'
