"""Read-only canonical import provider. No credentials or sample fallback."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from common.config import get_config, PROJECT_ROOT

TABLE_KEYS = {'requirements':'req_id', 'design_specs':'spec_id', 'bom_items':'part_id',
              'suppliers':'supplier_id', 'test_plans':'test_id', 'observations':'observation_id'}
UNITS = {'km','Wh/kg','degC','score','USD/kWh','Mohm','V','A','Ah','kWh','kg','mm','s','%','ohm','kW','N','cycles'}

class SourceUnavailable(RuntimeError):
    pass


def _finite(value):
    return isinstance(value, (int,float)) and not isinstance(value,bool) and math.isfinite(value)


def _validate(snapshot):
    def check(condition, message):
        if not condition:
            raise SourceUnavailable(message)
    check(isinstance(snapshot,dict), 'Canonical source must be an object')
    check(snapshot.get('schema_version') == 'npi-pilot-v1', 'Unsupported pilot source schema')
    check(snapshot.get('source_kind') == 'actual', 'Pilot source must explicitly identify actual records')
    for key in ('source_id','revision_id','extracted_at','provenance'):
        check(isinstance(snapshot.get(key),str) and bool(snapshot[key].strip()), 'Missing source identity, revision, timestamp or provenance')
    try:
        check(datetime.fromisoformat(snapshot['extracted_at'].replace('Z','+00:00')).tzinfo is not None, 'Extraction timestamp requires a timezone')
    except (ValueError, TypeError):
        raise SourceUnavailable('Invalid extraction timestamp') from None
    program = snapshot.get('program')
    check(isinstance(program,dict) and isinstance(program.get('program_id'),str) and bool(program['program_id']), 'Missing canonical program')
    pid = program['program_id']
    check(bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',pid)), 'Invalid canonical program key')
    check(not pid.startswith('PACK-ATLAS') and '@' not in pid, 'Demo program identities are not accepted as actual pilot programs')
    for key in ('name','vehicle_platform','stage','gate_status'):
        check(isinstance(program.get(key),str) and bool(program[key]), 'Incomplete program record')
    indexes = {}
    for table, key in TABLE_KEYS.items():
        rows = snapshot.get(table)
        check(isinstance(rows,list) and len(rows) <= 10000, 'Missing or oversized canonical source table: '+table)
        check(all(isinstance(r,dict) and isinstance(r.get(key),str) and bool(r[key]) for r in rows), 'Missing source record key: '+table)
        check(len({r[key] for r in rows}) == len(rows), 'Duplicate source record key: '+table)
        for row in rows:
            check(row.get('program_id') == pid and row.get('revision_id') == snapshot['revision_id'], 'Program/revision mismatch: '+table)
            check(row.get('source_id') == snapshot['source_id'] and isinstance(row.get('provenance'),str) and bool(row['provenance']), 'Missing record provenance: '+table)
            if table in {'requirements','design_specs','test_plans','observations'}:
                check(row.get('unit') in UNITS, 'Unknown or missing unit: '+table)
        check(all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',r[key]) for r in rows), 'Invalid canonical record key: '+table)
        indexes[table] = {r[key]:r for r in rows}
    check(bool(snapshot['requirements']), 'Pilot source has no requirements')
    reqs, specs, plans = indexes['requirements'], indexes['design_specs'], indexes['test_plans']
    for req in reqs.values():
        check(_finite(req.get('target_value')) and req['target_value'] > 0, 'Requirement target must be positive and finite')
        check(req.get('acceptance_direction') in {'higher','lower'}, 'Missing requirement acceptance direction')
        check(all(isinstance(req.get(k),str) and bool(req[k]) for k in ('category','text','priority','status')), 'Incomplete requirement')
    for spec in specs.values():
        check(all(isinstance(spec.get(k),str) and bool(spec[k]) for k in ('parameter','version')), 'Incomplete design record')
        check(spec.get('req_id') in reqs and _finite(spec.get('value')), 'Broken design requirement or invalid design value')
        check(spec['unit'] == reqs[spec['req_id']]['unit'], 'Design/requirement unit mismatch')
    for supplier in indexes['suppliers'].values():
        check(all(isinstance(supplier.get(k),str) and bool(supplier[k]) for k in ('name','region')), 'Incomplete supplier record')
    for part in indexes['bom_items'].values():
        check(isinstance(part.get('name'),str) and bool(part['name']), 'Incomplete BOM record')
        check(part.get('spec_id') in specs and part.get('supplier_id') in indexes['suppliers'], 'Broken BOM design/supplier link')
        check(all(_finite(part.get(k)) and part[k] >= 0 for k in ('qty','unit_cost','mass_kg')), 'Invalid BOM quantity, cost or mass')
    for plan in plans.values():
        check(plan.get('req_id') in reqs, 'Broken test requirement link')
        req = reqs[plan['req_id']]
        check(plan['unit'] == req['unit'] and plan.get('acceptance_direction') == req['acceptance_direction'], 'Plan unit or direction mismatch')
        check(_finite(plan.get('target_value')) and plan['target_value']==req['target_value'], 'Plan target mismatch')
        check(isinstance(plan.get('method'),str) and bool(plan['method']), 'Missing test method')
    for obs in indexes['observations'].values():
        check(obs.get('test_id') in plans and _finite(obs.get('measured_value')), 'Broken observation test link or invalid measurement')
        check(obs['unit'] == plans[obs['test_id']]['unit'], 'Observation/plan unit mismatch')
        try:
            check(datetime.fromisoformat((obs.get('recorded_at') if isinstance(obs.get('recorded_at'),str) else '').replace('Z','+00:00')).tzinfo is not None, 'Observation timestamp requires a timezone')
        except (TypeError,ValueError):
            raise SourceUnavailable('Invalid observation timestamp') from None
    canonical = json.dumps(snapshot,sort_keys=True,separators=(',',':'),allow_nan=False)
    return {**snapshot, 'snapshot_id':'pilot-'+hashlib.sha256(canonical.encode()).hexdigest()[:16]}


def validate(snapshot):
    try:
        return _validate(snapshot)
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        raise SourceUnavailable('Malformed canonical source fields') from None


def load():
    cfg = get_config().get('pilot', {})
    provider = os.getenv('NPI_SOURCE_PROVIDER') or cfg.get('provider','unconfigured')
    if provider != 'canonical_import':
        raise SourceUnavailable('Pilot source provider is not configured; no demo fallback is permitted')
    filename = os.getenv('NPI_PILOT_SOURCE') or cfg.get('import_path')
    if not filename:
        raise SourceUnavailable('Pilot canonical import path is not configured')
    path = Path(filename)
    if not path.is_absolute():
        path = Path(PROJECT_ROOT)/path
    try:
        if path.stat().st_size > 10*1024*1024:
            raise SourceUnavailable('Pilot source exceeds the 10 MiB import limit')
        return validate(json.loads(path.read_text()))
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        raise SourceUnavailable('Pilot source is unavailable or invalid; no demo fallback is permitted') from None


def readiness():
    try:
        snapshot = load()
        return {'state':'ready','provider':'canonical_import','source_id':snapshot['source_id'],
                'snapshot_id':snapshot['snapshot_id'],'revision_id':snapshot['revision_id'],
                'extracted_at':snapshot['extracted_at'],'provenance':snapshot['provenance'],
                'freshness':'not_checked', 'source_ready':True,'review_ready':False,
                'detail':'Validated read-only records; pilot review rules and model remain unavailable'}
    except SourceUnavailable as error:
        return {'state':'unready','source_ready':False,'review_ready':False,'provider':'canonical_import' if (os.getenv('NPI_SOURCE_PROVIDER') or get_config().get('pilot',{}).get('provider'))=='canonical_import' else 'unconfigured','detail':str(error)}


if __name__ == '__main__':
    assert 'observations' in TABLE_KEYS and 'degC' in UNITS
    assert issubclass(SourceUnavailable, RuntimeError)
    print('Pilot source contract OK')
