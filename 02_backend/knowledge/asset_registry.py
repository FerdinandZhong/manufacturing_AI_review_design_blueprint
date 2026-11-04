"""Canonical generated report identities and explicit evidence applicability."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
from common import source
from engineering.test_bench import _verdict

def generated_reports(program_id=None):
    keys = [program_id] if program_id else [s['program_key'] for s in source.list_scenarios()] + ['PACK-ORION-00','PACK-VEGA-00']
    out = []
    for key in keys:
        identity = source.snapshot_identity(key)
        for p in source.list_test_plans(key):
            samples = [o for o in source.list_observations(key) if o['test_id']==p['test_id']]
            if not samples:
                continue
            mean = round(sum(o['measured_value'] for o in samples)/len(samples),4)
            report = {**identity, 'test_plan':p, 'observation_ids':[o['observation_id'] for o in samples],
                      'measured_value':mean, 'unit':p['unit'], 'aggregation':'mean',
                      'verdict':_verdict(mean,float(p['target_value']),p.get('acceptance_direction','higher')),
                      'origin':'Generated direct demo evidence; not physical laboratory evidence'}
            aid = ('AST-'+key.split('-')[1]+'-thermal-report') if 'thermal' == p['req_id'].split('-')[-1] and '@' not in key else 'REPORT-'+identity['revision_id']+'-'+p['test_id']
            if key.startswith('PACK-VEGA') and aid.startswith('AST-'):
                aid = 'REPORT-VEGA-'+p['test_id']
            out.append(dict(asset_id=aid, ontology_class='TestReport', modality='text', title=f"{key} · {p['test_id']} · {report['verdict']}", caption_text=f"Generated validation report {p['test_id']}: {mean:g} {p['unit']}; {p['standard']}; {report['verdict']}", blob=json.dumps(report, sort_keys=True,indent=2).encode(), program_ref=key, linked_entity_type='Requirement', linked_entity_id=p['req_id'], provenance=report['origin'], source_url='', license_url='', evidence_kind='direct_demo', snapshot_id=identity['snapshot_id']))
    return out

def scope_kind(asset, program_id):
    if asset.get('source_url'):
        return 'external_reference'
    return 'direct_demo' if asset['program_ref']==program_id else 'historical_demo'

def scoped_assets(assets, program_id, kind='all', k=20):
    identity = source.snapshot_identity(program_id)
    groups = {'direct_demo':[], 'external_reference':[], 'historical_demo':[]}
    for asset in assets:
        if asset['program_ref'] not in {program_id,'PACK-ORION-00','PACK-VEGA-00','EXTERNAL-REFERENCE'}:
            continue
        category = scope_kind(asset,program_id)
        if category=='direct_demo' and asset.get('snapshot_id') and asset['snapshot_id']!=identity['snapshot_id']:
            continue
        if category=='historical_demo' and asset.get('snapshot_id') and asset['snapshot_id']!=source.snapshot_identity(asset['program_ref'])['snapshot_id']:
            continue
        if kind!='all' and kind!=category:
            continue
        groups[category].append({**asset,'evidence_kind':category})
    output = []
    while any(groups.values()) and len(output)<k:
        for rows in groups.values():
            if rows and len(output)<k:
                output.append(rows.pop(0))
    return output

if __name__ == '__main__':
    reports = generated_reports('PACK-ATLAS-01@atlas-v2')
    assert len(reports)==24
    assert all(json.loads(r['blob'])['test_plan']['standard'] in r['caption_text'] for r in reports)
    print('Canonical report registry OK')
