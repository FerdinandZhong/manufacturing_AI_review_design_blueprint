"""Build immutable engineering revisions. Observations never use design values."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import copy
import hashlib
import json
import random
from pathlib import Path
from data_generation.generate_synthetic_data import build_rows

ROOT = Path(__file__).resolve().parents[2]
BASE = 'PACK-ATLAS-01'
SCENARIOS = [('baseline', 'Original baseline'), ('atlas-v2', 'Expanded validation'), ('atlas-v3', 'Revised design')]
DOMAINS = [
    ('range', 'Urban driving range', 450, 'km', 'higher'),
    ('energy_density', 'Usable energy density', 180, 'Wh/kg', 'higher'),
    ('thermal', 'Coolant temperature rise', 12, 'degC', 'lower'),
    ('safety', 'Insulation resistance', 500, 'Mohm', 'higher'),
    ('cost', 'Assembly cost', 120, 'USD/kWh', 'lower'),
]

def build_snapshots():
    from common.runtime import require_demo
    require_demo('Synthetic artifact generation')
    random.seed(42)
    tables = dict(zip(['programs','requirements','design_specs','bom_items','suppliers','test_plans'], build_rows()))
    snapshots = []
    for revision, label in SCENARIOS:
        pid = BASE if revision == 'baseline' else BASE + '@' + revision
        data = {k: copy.deepcopy([r for r in rows if r.get('program_id', BASE) == BASE]) for k, rows in tables.items() if k != 'programs'}
        program = copy.deepcopy(tables['programs'][0])
        program.update(program_id=pid, revision_id=revision, base_program_id=BASE, scenario_label=label)
        for r in data['requirements']:
            r.update(acceptance_direction='higher', revision_id=revision)
        for p in data['test_plans']:
            p.update(acceptance_direction='higher', aggregation='mean', revision_id=revision)
        if revision != 'baseline':
            engineering_targets = {'range':450., 'energy_density':180., 'thermal':10., 'safety':500., 'cost':120.}
            for req, spec in zip(data['requirements'], data['design_specs']):
                category = req['category']
                target = engineering_targets[category]
                direction = 'lower' if category=='cost' else 'higher'
                req.update(target_value=target, acceptance_direction=direction)
                if category=='thermal':
                    req['text'] = 'Thermal headroom above the declared cooling design limit'
                    spec['parameter'] = 'thermal_headroom'
                spec['value'] = round(target * ({'range':1.20,'energy_density':1.18,'thermal':1.03,'safety':1.22,'cost':.88}[category]),4)
            for plan in data['test_plans']:
                category = plan['req_id'].split('-')[-1]
                plan['target_value'] = engineering_targets[category]
            for i in range(25):
                category, text, target, unit, direction = DOMAINS[i % 5]
                rid = f'REQ-ATLAS-{category}-{i // 5 + 2:02}'
                sid = rid.replace('REQ-', 'DS-')
                data['requirements'].append(dict(req_id=rid, program_id=pid, category=category, text=f'{text}, validation condition {i // 5 + 1}', target_value=target, unit=unit, priority='P0' if category in ('thermal','safety') else 'P1', source='seeded_engineering_specification', status='APPROVED', acceptance_direction=direction, revision_id=revision))
                data['design_specs'].append(dict(spec_id=sid, program_id=pid, req_id=rid, parameter=text.lower().replace(' ','_'), value=round(target * (0.82 if direction == 'lower' else 1.18),4), unit=unit, rationale='Seeded design allocation; independent from validation observations', cell_chemistry='NMC811', version=revision))
                if i < 20 or revision == 'atlas-v3':
                    data['test_plans'].append(dict(test_id=rid.replace('REQ-','T-')+'-01', program_id=pid, req_id=rid, method=f'{category}_bench_test', standard=['UN38.3','GB 38031','IEC 62660','ISO-12405'][i%4], pass_criteria='directional margin >= 0.10; marginal >= 0', target_value=target, unit=unit, acceptance_direction=direction, aggregation='mean', revision_id=revision))
            # A second component exercises one-to-many BOM aggregation.
            data['bom_items'] = []
            for i, spec in enumerate(data['design_specs']):
                for j in range(2 if i < 18 else 1):
                    data['bom_items'].append(dict(part_id=f'BOM-ATLAS-{i:02}-{j+1:02}', program_id=pid, spec_id=spec['spec_id'], name=f"{spec['parameter']} component {j+1}", supplier_id=f'SUP-{i%5+1:02}', qty=j+1, unit_cost=round(35+i*2.4+j*8,2), mass_kg=round(0.8+i*.15+j*.2,3)))
            if revision == 'atlas-v3':
                data['design_specs'][2]['value'] = 12.2
                data['design_specs'][2]['version'] = revision
                data['test_plans'].append(dict(test_id='T-ATLAS-cost-01', program_id=pid, req_id='REQ-ATLAS-cost', method='cost_audit', standard='internal', pass_criteria='directional margin >= 0.10', target_value=120., unit='USD/kWh', acceptance_direction='lower', aggregation='mean', revision_id=revision))
        # The observation basis is an independent, seeded laboratory fixture.
        # Original baseline values are pinned for regression, not copied from specs.
        observation_basis = {'range':120., 'energy_density':118., 'thermal':103., 'safety':122.}
        if revision != 'baseline':
            observation_basis = {'range':540., 'energy_density':212.4, 'thermal':10.3, 'safety':610.}
        observations = []
        for p in data['test_plans']:
            original = p['test_id'] in {f'T-ATLAS-{c}-01' for c in observation_basis}
            center = observation_basis[p['req_id'].split('-')[-1]] if original else float(p['target_value']) * (0.80 if p['acceptance_direction']=='lower' else 1.20)
            if revision == 'atlas-v3' and p['req_id']=='REQ-ATLAS-thermal':
                center = 12.1
            for run in range(8):
                observations.append(dict(observation_id=f"OBS-{revision}-{p['test_id']}-{run+1:02}", test_id=p['test_id'], program_id=pid, revision_id=revision, measured_value=round(center + (run-3.5)*abs(float(p['target_value']))*.001,5), unit=p['unit'], run_id=f'RUN-{revision}-{run+1:02}', recorded_at=f'2026-09-{run+10:02}T09:00:00Z', origin='seeded_independent_observation', replicate=run%2+1, condition_id=f'COND-{run//2+1:02}', ambient_temperature_c=[-20,0,25,45][run//2], cycle_count=[0,100,500,1000][run//2]))
        for rows in data.values():
            for r in rows:
                if 'program_id' in r:
                    r['program_id'] = pid
        data['observations'] = observations
        data['issues'] = [] if revision=='baseline' else [dict(issue_id='ISS-ATLAS-THERMAL', program_id=pid, req_id='REQ-ATLAS-thermal', title='Thermal validation margin requires corrective action', status='CLOSED' if revision=='atlas-v3' else 'OPEN', action_id='CA-ATLAS-COOLING', owner='Thermal engineering', corrective_action='Revise cooling plate and validate independent follow-up runs', verification_test_id='T-ATLAS-thermal-01', resolved_revision='atlas-v3' if revision=='atlas-v3' else None)]
        data['history'] = [dict(revision_id=r, parent_revision=SCENARIOS[n-1][0] if n else None, change=title) for n,(r,title) in enumerate(SCENARIOS) if n <= [x[0] for x in SCENARIOS].index(revision)]
        payload = dict(source_contract_version='engineering-v2', metric_contract_version='metrics-v2', program=program, **data)
        payload['snapshot_id'] = 'snap-' + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',',':')).encode()).hexdigest()[:16]
        snapshots.append(payload)
    return snapshots

def generate(out_dir=None):
    from common.runtime import require_demo
    require_demo('Synthetic snapshot generation')
    target = Path(out_dir) if out_dir else ROOT/'data/raw/snapshots'
    target.mkdir(parents=True, exist_ok=True)
    snapshots = build_snapshots()
    for s in snapshots:
        (target/(s['program']['revision_id']+'.json')).write_text(json.dumps(s, indent=2, sort_keys=True)+'\n')
    return snapshots

if __name__ == '__main__':
    rows = generate()
    assert len(rows[1]['requirements']) == 30
    assert len(rows[1]['observations']) == 192
    assert len(rows[1]['bom_items']) == 48
    assert rows == build_snapshots()
    print('Engineering snapshots OK: baseline, expanded, revised')
