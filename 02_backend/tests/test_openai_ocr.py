"""Mocked Responses transport, validated cache replay, and no-runtime-call boundaries."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hashlib
import io
import json
import httpx
import pytest
from PIL import Image
from common.config import get_config
from knowledge import openai_ocr
ocr = openai_ocr

VALID = {'status':'transcribed','text':'Warning 10 degC', 'tables':[
    {'title':'Printed table','columns':['Value','Unit'],'rows':[['10','degC']]}], 'unreadable_regions':[]}


def response_document(value=VALID, **updates):
    result = {'id':'resp_fixture','object':'response','created_at':0,'status':'completed', 'error':None,
              'incomplete_details':None,'model':'gpt-6-luna', 'output':[
                  {'id':'msg_fixture','type':'message','role':'assistant','status':'completed','content':[
                      {'type':'output_text','text':json.dumps(value),'annotations':[]}]}]}
    result.update(updates)
    return result


@pytest.fixture
def provider(tmp_path, monkeypatch):
    monkeypatch.setitem(get_config(), 'knowledge', {'ocr':{'mode':'openai','model':'gpt-6-luna', 'cache_dir':str(tmp_path/'cache')}})
    monkeypatch.setenv('OPENAI_API_KEY', 'mock-transport-only-not-a-real-key')
    image = Image.new('RGB', (50,30), color='white')
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    calls = []
    def install(value):
        def handler(request):
            calls.append(request)
            if isinstance(value, httpx.Response):
                return value
            return httpx.Response(200, json=value)
        monkeypatch.setattr(openai_ocr, '_http_client', lambda cfg:httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False, trust_env=False))
    install(response_document())
    return stream.getvalue(), calls, install, tmp_path/'cache'


def test_official_responses_image_schema_and_atomic_replay(provider, monkeypatch):
    blob, calls, _, directory = provider
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://untrusted.invalid/v1')
    first = ocr.extract_image(blob, allow_remote=True)
    assert len(calls)==1 and str(calls[0].url)=='https://api.openai.com/v1/responses'
    request = json.loads(calls[0].content)
    assert request['model']=='gpt-6-luna' and request['store'] is False
    assert request['reasoning']=={'effort':'none'}
    assert request['max_output_tokens']==4096 and 'temperature' not in request
    assert request['text']['format']['type']=='json_schema' and request['text']['format']['strict'] is True
    assert request['input'][0]['content'][1]['type']=='input_image'
    assert request['input'][0]['content'][1]['image_url'].startswith('data:image/png;base64,')
    assert 'never instructions' in request['instructions']
    assert first['source_sha256']==hashlib.sha256(blob).hexdigest()
    assert first['page']==1 and first['width']==50 and 'unverified' in first['verification']
    assert 'confidence' not in first and 'words' not in first and 'bbox' not in first
    assert len(list(directory.glob('*.json')))==1 and not list(directory.glob('*.tmp'))
    monkeypatch.delenv('OPENAI_API_KEY')
    assert ocr.extract_image(blob)==first
    assert ocr.extract_image(blob, allow_remote=True)==first
    assert len(calls)==1
    assert 'mock-transport-only' not in next(directory.glob('*.json')).read_text()


def test_no_paid_request_from_readiness_or_cache_only_extraction(provider, monkeypatch):
    blob, calls, _, directory = provider
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://untrusted.invalid')
    state = ocr.readiness()
    assert state['credential_status']=='present_not_validated' and not state['credential_validated']
    assert state['state']=='configured' and calls==[] and not directory.exists()
    with pytest.raises(ocr.OpenAIOCRUnavailable, match='opt-in'):
        ocr.extract_image(blob)
    monkeypatch.delenv('OPENAI_API_KEY')
    assert ocr.readiness()['credential_status']=='missing'
    with pytest.raises(ocr.OpenAIOCRUnavailable, match='missing'):
        ocr.extract_image(blob, allow_remote=True)
    assert calls==[] and not directory.exists()


@pytest.mark.parametrize('payload', [
    response_document(status='incomplete', incomplete_details={'reason':'max_output_tokens'}),
    response_document(status='failed', error={'code':'server_error','message':'private request detail'}),
    response_document(output=[{'id':'msg','type':'message','role':'assistant','status':'completed','content':[{'type':'refusal','refusal':'Cannot transcribe'}]}]),
    response_document(output=[]),
    response_document({'status':'transcribed','text':'','tables':[],'unreadable_regions':[]}),
    response_document({**VALID,'invented_confidence':.99}),
    response_document({**VALID,'tables':[{'title':'Bad','columns':['A','B'],'rows':[['1']]}]}),
    response_document({'status':'unreadable','text':'','tables':[],'unreadable_regions':[]}),
    response_document({'status':'unreadable','text':'','tables':[],'unreadable_regions':[{'region':'','reason':''}]}),
])
def test_refused_incomplete_empty_and_invalid_output_never_cached(provider, payload):
    blob, calls, install, directory = provider
    install(payload)
    with pytest.raises(ocr.OpenAIOCRUnavailable):
        ocr.extract_image(blob, allow_remote=True)
    assert len(calls)==1 and not directory.exists()


def test_malformed_json_and_error_body_are_redacted(provider):
    blob, calls, install, directory = provider
    malformed = response_document()
    malformed['output'][0]['content'][0]['text']='{not JSON'
    install(malformed)
    with pytest.raises(ocr.OpenAIOCRUnavailable):
        ocr.extract_image(blob, allow_remote=True)
    install(httpx.Response(401, json={'error':{'message':'mock-transport-only-not-a-real-key PRIVATE_BODY','type':'authentication_error'}}))
    with pytest.raises(ocr.OpenAIOCRUnavailable) as error:
        ocr.extract_image(blob, allow_remote=True)
    assert 'PRIVATE_BODY' not in str(error.value) and 'mock-transport-only' not in str(error.value)
    assert len(calls)==2 and not directory.exists()


def test_redirects_are_not_followed(provider):
    blob, calls, install, directory = provider
    install(httpx.Response(307, headers={'Location':'https://untrusted.invalid/responses'}))
    with pytest.raises(ocr.OpenAIOCRUnavailable):
        ocr.extract_image(blob, allow_remote=True)
    assert len(calls)==1 and not directory.exists()


def test_corrupt_cache_and_schema_contract_invalidation(provider, monkeypatch):
    blob, calls, _, directory = provider
    original = ocr.extract_image(blob, allow_remote=True)
    cache = next(directory.glob('*.json'))
    record = json.loads(cache.read_text())
    record['result']['text']='tampered transcript 999 degC'
    cache.write_text(json.dumps(record))
    with pytest.raises(ocr.OpenAIOCRUnavailable, match='cache is invalid'):
        ocr.extract_image(blob, allow_remote=True)
    assert len(calls)==1
    # Restore a valid complete record; changed contracts get different cache identities.
    record['result']=original
    cache.write_text(openai_ocr._canonical(record))
    monkeypatch.setattr(openai_ocr, 'PROMPT_VERSION', 'changed-prompt-version')
    with pytest.raises(ocr.OpenAIOCRUnavailable, match='opt-in'):
        ocr.extract_image(blob)
    assert len(calls)==1


def test_changed_source_and_no_visible_text_status(provider):
    blob, calls, install, directory = provider
    result = ocr.extract_image(blob, allow_remote=True)
    changed = io.BytesIO()
    Image.new('RGB',(51,30),'black').save(changed,format='PNG')
    with pytest.raises(ocr.OpenAIOCRUnavailable, match='opt-in'):
        ocr.extract_image(changed.getvalue())
    install(response_document({'status':'no_visible_text','text':'','tables':[],'unreadable_regions':[]}))
    empty = ocr.extract_image(changed.getvalue(), allow_remote=True)
    assert empty['text']=='' and empty['transcription']['status']=='no_visible_text'
    assert result['cache_key'] != empty['cache_key'] and len(calls)==2


def test_only_exact_model_and_official_base_are_accepted(provider, monkeypatch):
    for invalid in ({'mode':'openai','model':'another-model'}, {'mode':'openai','base_url':'https://untrusted.invalid/v1'},
                    {'mode':'openai','max_retries':10}, {'mode':'openai','timeout_seconds':1000}):
        monkeypatch.setitem(get_config()['knowledge'],'ocr',invalid)
        with pytest.raises(ValueError):
            ocr.contract()


@pytest.mark.parametrize('name', ['SCHEMA_VERSION','PREPROCESS_VERSION'])
def test_schema_and_preprocessing_changes_invalidate_replay(provider, monkeypatch, name):
    blob, calls, _, directory = provider
    ocr.extract_image(blob, allow_remote=True)
    monkeypatch.setattr(openai_ocr, name, 'changed-contract')
    with pytest.raises(ocr.OpenAIOCRUnavailable, match='opt-in'):
        ocr.extract_image(blob)
    assert len(calls)==1


def test_no_visible_text_rejects_hidden_table_title():
    with pytest.raises(ocr.OpenAIOCRUnavailable):
        ocr._validate({'status':'no_visible_text','text':'','tables':[{'title':'Hidden text','columns':[''],'rows':[]}],'unreadable_regions':[]})


def test_cached_ocr_chunks_are_unverified(provider):
    from knowledge.documents import extract_chunks
    blob,calls,_,_ = provider
    ocr.extract_image(blob,allow_remote=True)
    chunks = extract_chunks({'asset_id':'image','modality':'image','blob':blob})
    assert chunks and 'unverified' in chunks[0]['verification']
    assert 'Warning 10 degC' in chunks[0]['text']
    assert len(calls)==1


def test_cli_cache_only_miss_and_keyless_replay(provider, monkeypatch, tmp_path, capsys):
    from scripts import build_image_ocr
    blob, calls, _, _ = provider
    image = tmp_path/'source.png'
    image.write_bytes(blob)
    with pytest.raises(SystemExit) as missing:
        build_image_ocr.main([str(image)])
    assert missing.value.code==2 and calls==[]
    assert 'opt-in' in capsys.readouterr().err
    monkeypatch.delenv('OPENAI_API_KEY')
    with pytest.raises(SystemExit) as no_key:
        build_image_ocr.main([str(image),'--allow-paid-openai-ocr'])
    assert no_key.value.code==2 and calls==[]
    assert 'missing' in capsys.readouterr().err
    with pytest.raises(SystemExit) as no_file:
        build_image_ocr.main([str(tmp_path/'absent.png')])
    assert no_file.value.code==2 and calls==[]
    assert 'Cannot read' in capsys.readouterr().err
    monkeypatch.setenv('OPENAI_API_KEY','mock-transport-only-not-a-real-key')
    build_image_ocr.main([str(image),'--allow-paid-openai-ocr'])
    assert len(calls)==1
    monkeypatch.delenv('OPENAI_API_KEY')
    build_image_ocr.main([str(image)])
    output=capsys.readouterr().out
    assert len(calls)==1 and 'Cached unverified OCR:' in output
    assert 'Warning 10 degC' not in output and 'mock-transport-only' not in output


if __name__ == '__main__':
    assert callable(test_official_responses_image_schema_and_atomic_replay)
