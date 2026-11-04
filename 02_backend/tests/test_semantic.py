"""Semantic joins and AI evidence boundaries, isolated from the runtime database."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from common import db
from knowledge import semantic
from api.main import app


@pytest.fixture
def prepared(monkeypatch, tmp_path):
    monkeypatch.setattr(db, 'get_db_path', lambda: str(tmp_path / 'ops.db'))
    db.init_db()
    from engineering.test_bench import run_test_bench
    run_test_bench('PACK-ATLAS-01')
    monkeypatch.setattr(semantic.risk_model, 'get_scores', lambda pid: [
        {'entity_id': 'REQ-ATLAS-thermal', 'risk_band': 'HIGH', 'risk_prob': 1.0, 'program_id': pid},
        {'entity_id': 'REQ-ATLAS-range', 'risk_band': 'LOW', 'risk_prob': 0.0, 'program_id': pid},
    ])
    return TestClient(app)


def test_real_reference_files_have_matching_checksums():
    manifest = semantic.reference_manifest()
    assert manifest['source_id'] and manifest['license_url']
    for asset in manifest['assets']:
        blob = (semantic.REFERENCES / asset['file']).read_bytes()
        assert hashlib.sha256(blob).hexdigest() == asset['sha256']
        assert asset['source_url'] and asset['locator']
        if asset['modality'] == 'image':
            assert blob.startswith(b'\xff\xd8')
        elif asset['modality'] == 'pdf':
            assert blob.startswith(b'%PDF')
    rows = semantic.reference_rows()
    assert len(rows) == 11
    assert {r['chemistry'] for r in rows} == {'LMO'}
    assert next(r for r in rows if r['experiment_id'] == '7')['peak_cell_temperature_c'] == 500
    assert next(r for r in rows if r['experiment_id'] == '11')['total_gas_mol'] == 5.9


def test_context_joins_and_reproducible_fingerprint(prepared):
    first = semantic.context()
    assert first == semantic.context()
    records = first['packet']['records']
    req = records['requirement']['req_id']
    assert req == 'REQ-ATLAS-thermal'
    assert all(d['req_id'] == req for d in records['design'])
    assert all(t['req_id'] == req for t in records['test']['plans'])
    assert all(s['entity_id'] == req for s in records['risk'])
    assert records['test']['results'][0]['verdict'] == 'MARGINAL'
    assert all(r['source_id'] != 'PACK-ATLAS-01' for r in first['measurements'])
    assert any(e['kind'] == 'curated_reference' for e in first['graph']['edges'])
    assert first['packet']['concept']['boundary']
    assert semantic.context(question_id='venting')['context_sha256'] != first['context_sha256']


def test_ai_receives_context_without_controlling_facts(prepared, monkeypatch):
    from agents import llm_client
    captured = []
    monkeypatch.setattr(llm_client, 'chat', lambda messages, stream=False: captured.append(messages) or 'Atlas has MARGINAL thermal result [F-TEST].')
    baseline = semantic.context()
    result = semantic.explain(narration='model')
    assert result['narration'] == 'configured language model'
    assert result['packet'] == baseline['packet']
    assert 'Table 2' in captured[0][1]['content']
    assert 'constraints' in captured[0][1]['content']
    assert 'MARGINAL' in captured[0][1]['content']
    assert semantic.context()['packet'] == baseline['packet']


def test_vision_sends_real_image_bytes_only_when_requested(prepared, monkeypatch):
    from agents import llm_client
    captured = []
    monkeypatch.setattr(llm_client, 'chat', lambda messages, stream=False: captured.append(messages) or 'Image reference [RES-cell-before-after].')
    result = semantic.explain(narration='model', include_images=True)
    assert result['narration'] == 'configured model with image input'
    images = [p for p in captured[0][1]['content'] if p['type'] == 'image_url']
    assert len(images) == 2
    assert all(p['image_url']['url'].startswith('data:image/jpeg;base64,/9j/') for p in images)
    assert 'base64' not in json.dumps(result['prompt'])


def test_model_failure_is_explicit_template(prepared, monkeypatch):
    from agents import llm_client
    def fail(*args, **kwargs):
        raise RuntimeError('secret endpoint credential')
    monkeypatch.setattr(llm_client, 'chat', fail)
    result = semantic.explain(narration='model')
    assert result['narration'] == 'deterministic template'
    assert result['answer'] == semantic.explain()['answer']
    assert 'unavailable' in result['note'] and 'secret' not in result['note']


def test_api_scope_assets_and_inputs(prepared):
    assert prepared.get('/api/semantic/context').status_code == 200
    assert prepared.get('/api/semantic/context?question_id=inject').status_code == 422
    assert prepared.post('/api/semantic/explain', json={'question_id': 'applicability'}).json()['answer'].startswith('No.')
    assert prepared.post('/api/semantic/explain', json={'include_images': True}).status_code == 422
    assert prepared.get('/api/semantic/assets/unknown').status_code == 404
    for asset in semantic.reference_manifest()['assets']:
        result = prepared.get('/api/semantic/assets/' + asset['id'])
        assert result.status_code == 200
        assert result.headers['content-type'].startswith(asset['mime_type'])
    assert prepared.get('/api/semantic/experiments.csv').status_code == 200


def test_other_programs_do_not_inherit_atlas_context():
    from agents.tools import get_semantic_context
    result = get_semantic_context(None, 'PACK-ORION-00')
    assert 'records' not in result
    assert 'only for PACK-ATLAS-01' in result['constraints'][0]


def test_missing_research_does_not_block_graph_or_photographs(prepared, monkeypatch, tmp_path):
    monkeypatch.setattr(semantic, 'REFERENCES', tmp_path)
    data = semantic.context()
    assert data['measurements'] == []
    assert len([a for a in data['evidence'] if a['id'].startswith('REF-')]) == 5
    assert len([a for a in data['evidence'] if a.get('evidence_kind') == 'direct_demo']) == 1
    assert data['research_state'] == 'missing'
    assert next(q for q in data['model']['questions'] if q['id'] == 'venting')['enabled'] is False
    assert prepared.get('/api/semantic/model').status_code == 200
    assert prepared.get('/api/semantic/context').status_code == 200
    assert prepared.post('/api/semantic/explain', json={'question_id': 'packaging'}).status_code == 200
    assert prepared.post('/api/semantic/explain', json={'question_id': 'venting'}).status_code == 422
    assert prepared.get('/api/semantic/experiments.csv').status_code == 404


def test_corrupt_photo_is_disabled_without_losing_graph(prepared, monkeypatch, tmp_path):
    import shutil
    shutil.copytree(semantic.PHOTOS, tmp_path / 'photos')
    monkeypatch.setattr(semantic, 'PHOTOS', tmp_path / 'photos')
    (semantic.PHOTOS / 'leaf-pack.jpg').write_bytes(b'corrupt')
    data = semantic.context()
    assert next(s for s in data['source_states'] if s['id'] == 'REF-leaf-pack')['state'] == 'invalid checksum'
    assert all(a['id'] != 'REF-leaf-pack' for a in data['evidence'])
    assert prepared.get('/api/semantic/assets/REF-leaf-pack').status_code == 409


def test_unknown_model_citation_uses_template(prepared, monkeypatch):
    from agents import llm_client
    monkeypatch.setattr(llm_client, 'chat', lambda *a, **k: 'Unsupported claim [invented].')
    result = semantic.explain(narration='model', include_images=True)
    assert result['narration'] == 'deterministic template'
    assert result['image_inputs'] == []


def test_exact_program_bom_join_and_photo_boundary(prepared):
    data = semantic.context(question_id='packaging')
    assert all(p['program_id'] == 'PACK-ATLAS-01' for p in data['packet']['records']['part'])
    assert any(e['id'] == 'program_part' and e['kind'] == 'exact_key' for e in data['graph']['edges'])
    assert all(a['experiment_ids'] == [] for a in data['evidence'] if a['id'].startswith('REF-'))
    assert all(l['kind'] == 'curated_reference' for l in data['packet']['evidence_links'])


def test_source_table_and_figure_links_are_explicit(prepared):
    data = semantic.context(question_id='venting')
    links = [l for l in data['packet']['evidence_links'] if l['kind'] == 'source_locator']
    assert [l['experiment_id'] for l in links if l['asset_id'] == 'RES-experiment-7'] == ['7']
    assert not [l for l in links if l['asset_id'] == 'RES-cell-before-after']
    excerpt = next(a for a in data['packet']['records']['evidence'] if a['id'] == 'RES-study-excerpt')
    assert 'Table 2' in excerpt['source_text'] and '500' in excerpt['source_text']


def test_changed_measurement_is_invalid_even_with_updated_csv_checksum(prepared, monkeypatch, tmp_path):
    import shutil
    shutil.copytree(semantic.REFERENCES, tmp_path / 'reference')
    monkeypatch.setattr(semantic, 'REFERENCES', tmp_path / 'reference')
    csv_path = semantic.REFERENCES / 'experiments.csv'
    csv_path.write_text(csv_path.read_text().replace('531,3.2', '999,3.2'))
    manifest_path = semantic.REFERENCES / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['measurements_sha256'] = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    assert semantic.research_validation()['state'] == 'invalid'
    assert semantic.context()['measurements'] == []


@pytest.mark.parametrize('content', ['{broken', '{}', '{"source_id":"x","assets":[{}]}'])
def test_malformed_research_manifest_keeps_graph(prepared, monkeypatch, tmp_path, content):
    monkeypatch.setattr(semantic, 'REFERENCES', tmp_path)
    (tmp_path / 'manifest.json').write_text(content)
    data = semantic.context()
    assert data['research_state'] == 'invalid'
    assert len([a for a in data['evidence'] if a['id'].startswith('REF-')]) == 5
    assert len([a for a in data['evidence'] if a.get('evidence_kind') == 'direct_demo']) == 1
    assert prepared.get('/api/semantic/context').status_code == 200
    with pytest.raises(ValueError):
        semantic.reference_assets()


def test_retrieval_uses_question_specific_queries(prepared):
    thermal = semantic.context(question_id='thermal')['packet']['retrieval']['query']
    packaging = semantic.context(question_id='packaging')['packet']['retrieval']['query']
    assert thermal != packaging
    requirement = semantic.context()['packet']['records']['requirement']
    assert requirement['text'] in thermal
    assert requirement['text'] not in packaging


if __name__ == '__main__':
    assert semantic.contract()['version'] == 'npi-context-1.0'
