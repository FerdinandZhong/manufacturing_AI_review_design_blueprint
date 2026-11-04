"""Contract, extraction, scope, no-hit, and conservative claim regressions."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import pytest
import pyarrow as pa
import lance
from common.config import get_config
from knowledge import kb
from knowledge.documents import extract_chunks
from knowledge.narration_guard import validate_answer


def test_no_hit_and_offline_default(monkeypatch):
    monkeypatch.delitem(get_config(),'knowledge',raising=False)
    monkeypatch.setattr(kb,'_try_load_st',lambda: (_ for _ in ()).throw(AssertionError('model discovery')))
    kb.build_kb()
    assert kb.embedding_contract()['dimension']==128
    assert kb.search('!!!')==[]
    assert kb.search('the is of')==[]
    assert kb.search('xylophonicquasarabsent')==[]
    assert kb.search('thermal', k=0)==[]


def test_stale_embedding_contract_rejected():
    kb.build_kb()
    table=lance.dataset(kb._kb_path()).to_table()
    table=table.set_column(table.schema.get_field_index('embedding_contract'),'embedding_contract',pa.array(['{}']*table.num_rows))
    lance.write_dataset(table,kb._kb_path(),mode='overwrite')
    with pytest.raises(kb.IncompatibleIndex,match='prepare.py'):
        kb.search('thermal')
    kb.build_kb()


def test_text_body_extracted_and_stable():
    a={'asset_id':'body-only','modality':'text','blob':b'Hidden body term: quasarxyz'}
    first=extract_chunks(a)
    assert first==extract_chunks(a)
    assert first[0]['page']==1 and first[0]['source_sha256']
    changed=extract_chunks({**a,'blob':b'Other body'})
    assert first[0]['chunk_id']!=changed[0]['chunk_id']


def test_scope_and_requirement_filter_before_top_k():
    kb.build_kb()
    hits=kb.search('thermal',k=1,program_id='PACK-ATLAS-01@atlas-v2',evidence_kind='direct_demo',requirement_ids=['REQ-ATLAS-thermal'])
    assert len(hits)==1
    assert hits[0]['program_ref']=='PACK-ATLAS-01@atlas-v2'
    assert hits[0]['linked_entity_id']=='REQ-ATLAS-thermal'
    assert hits[0]['retrieval']['chunks']
    assert kb.search('thermal',program_id='PACK-ATLAS-01',evidence_kind='direct_demo',requirement_ids=['absent'])==[]


@pytest.fixture
def packet():
    return {'facts':[{'id':'F-TEST','value':'MARGINAL'},{'id':'F-RISK','value':'HIGH'}, {'id':'F-REQ','value':'10 degC'}], 'records':{'evidence':[{'id':'image','caption':'External image reference.'}]}}


@pytest.mark.parametrize('text',[
    'Atlas shows a MARGINAL thermal bench result [F-TEST].',
    'The Atlas program records a HIGH design-risk band [F-RISK].',
    'Atlas specifies a thermal target of 10 degC [F-REQ].',
    'Source image reference [image].',
])
def test_supported_paraphrased_claims(packet,text):
    assert validate_answer(text,packet)==text


@pytest.mark.parametrize('text',[
    'Atlas shows a PASS thermal result [F-TEST].',
    'Atlas has a MARGINAL thermal result at 999 degC [F-TEST].',
    'Atlas specifies a thermal target of 10 V [F-REQ].',
    'Atlas has a HIGH thermal result [F-RISK].',
    'Atlas does not have a MARGINAL thermal result [F-TEST].',
    'Orion has a MARGINAL thermal result [F-TEST].',
    'Atlas complies with requirements [image].',
    'Measured 10 degC [image].',
    'External research validates Atlas [image].',
])
def test_fabricated_or_misbound_claims_rejected(packet,text):
    with pytest.raises(ValueError):
        validate_answer(text,packet)


def test_gate_narration_never_yields_invalid_prefix(monkeypatch):
    from agents import narrative
    monkeypatch.setattr(narrative,'chat',lambda *a,**kw:'Gate PASS. Fabricated 999 V.')
    chunks=list(narrative.narrate('PACK-ATLAS-01',[], 'CONDITIONAL'))
    assert len(chunks)==1 and 'CONDITIONAL' in chunks[0]
    assert '999' not in chunks[0] and 'PASS' not in chunks[0]


def test_source_body_search_and_metadata_only_support(monkeypatch):
    from data_generation import generate_assets
    from knowledge import ontology
    asset={'asset_id':'body-fixture','ontology_class':ontology.classes()[0], 'modality':'text',
           'title':'Metadataonlyword', 'caption_text':'Caption', 'blob':b'Body contains quasaruniqueterm.',
           'program_ref':'PACK-ATLAS-01','linked_entity_type':'Requirement', 'linked_entity_id':'REQ-ATLAS-thermal',
           'provenance':'fixture','source_url':'','license_url':''}
    monkeypatch.setattr(generate_assets,'build_assets',lambda:[asset])
    kb.build_kb()
    hits=kb.search('quasaruniqueterm')
    assert len(hits)==1 and hits[0]['retrieval']['chunks'][0]['text'].startswith('Body')
    metadata=kb.search('Metadataonlyword')[0]
    assert metadata['retrieval']['chunks']==[]
    assert metadata['retrieval']['support'].startswith('metadata only')


def test_scanned_pdf_and_svg_metadata_limits():
    import io
    from pypdf import PdfWriter
    from knowledge.documents import extract_document
    writer=PdfWriter()
    writer.add_blank_page(width=100,height=100)
    stream=io.BytesIO()
    writer.write(stream)
    extracted=extract_document({'asset_id':'scan','modality':'pdf','blob':stream.getvalue()})
    assert extracted['state']=='partial_or_scanned' and extracted['chunks']==[]
    svg=extract_document({'asset_id':'svg','modality':'image','blob':b'<svg><title>Hidden</title><desc>Metadata</desc><text>Visible</text></svg>'})
    assert svg['chunks'][0]['text']=='Visible'
    assert svg['method']=='svg-text-markup-v1'


def test_stale_index_api_is_actionable():
    from fastapi.testclient import TestClient
    from api.main import app
    kb.build_kb()
    table=lance.dataset(kb._kb_path()).to_table().drop(['embedding_contract'])
    lance.write_dataset(table,kb._kb_path(),mode='overwrite')
    response=TestClient(app).get('/api/kb/search',params={'q':'thermal'})
    assert response.status_code==503
    assert response.json()['code']=='incompatible_knowledge_index'
    assert 'prepare.py' in response.json()['detail']
    kb.build_kb()


def test_prepare_without_knowledge_config_or_ocr_cache_is_offline(monkeypatch, tmp_path):
    from scripts import prepare
    from data_generation import generate_snapshots
    from knowledge import openai_ocr
    monkeypatch.delitem(get_config(),'knowledge',raising=False)
    monkeypatch.setitem(get_config()['data'],'kb_dir',str(tmp_path/'fresh-kb'))
    # Source snapshots already exist. Never write source files from a test.
    monkeypatch.setattr(generate_snapshots,'generate',lambda:None)
    monkeypatch.setattr(openai_ocr,'_request',lambda *args: (_ for _ in ()).throw(AssertionError('paid request')))
    prepare.main()
    assert kb.search('thermal')
    assert not (tmp_path/'fresh-kb'/'ocr_cache').exists()


def test_worker_query_uses_actual_requirement_text(monkeypatch):
    from agents import workers
    from common import source
    captured=[]
    monkeypatch.setattr(workers,'create_evidence',lambda *a,**kw:'evidence')
    monkeypatch.setattr(workers,'_llm_bullets',lambda system,user,fallback:fallback)
    monkeypatch.setitem(workers.TOOLS,'get_design_risk',lambda *a:[{'entity_id':'REQ-ATLAS-thermal','risk_prob':.9}])
    monkeypatch.setitem(workers.TOOLS,'get_semantic_context',lambda *a:{})
    monkeypatch.setattr(kb,'search',lambda query,**kw:captured.append((query,kw)) or [])
    workers.run_knowledgereuse_worker('review','PACK-ATLAS-01')
    req=next(r for r in source.list_requirements('PACK-ATLAS-01') if r['req_id']=='REQ-ATLAS-thermal')
    assert req['text'] in captured[0][0]
    assert captured[0][1]['requirement_ids']==['REQ-ATLAS-thermal']


if __name__ == '__main__':
    assert extract_chunks({'asset_id':'self','modality':'text','blob':b'body'})
