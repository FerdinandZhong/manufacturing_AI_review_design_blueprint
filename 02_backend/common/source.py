"""Source (reference) data access — programs/requirements/design/BOM/tests.

Backend is Iceberg in prod, local CSV as fallback (Phase 1: csv only). NO
SQLite for source data. Operational state (test_results/gate_reviews/
evidence/annotations/model registry) lives in the ops store (see
common/db.py), not here.

Config (config.yaml):
    source:
      backend: auto        # auto | iceberg | csv  (Phase 1: csv)
      csv_dir: data/raw
    demo:
      showcase_program_id: PACK-ATLAS-01
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "02_backend"))

import json
import hashlib
from pathlib import Path

import pandas as pd

from common.config import get_config, PROJECT_ROOT as CFG_PROJECT_ROOT

from common.runtime import data_mode
from common import providers

SOURCE_TABLES = ["programs", "requirements", "design_specs", "bom_items", "suppliers", "test_plans"]

_backend: str | None = None
_csv_cache: dict[str, pd.DataFrame] = {}


# ── backend resolution ────────────────────────────────────────────────────

def _source_cfg() -> dict:
    return get_config().get("source", {}) or {}


def backend() -> str:
    """Resolve the source backend once ('csv' for Phase 1)."""
    if data_mode() == 'pilot':
        providers.load()
        return 'canonical_import'
    global _backend
    if _backend is not None:
        return _backend
    want = _source_cfg().get("backend", "auto")
    if want == "iceberg":
        raise RuntimeError("iceberg backend not configured (Phase 1 is csv)")
    _backend = "csv"
    return _backend


# ── query helpers ─────────────────────────────────────────────────────────

def _csv(table: str) -> pd.DataFrame:
    if table not in _csv_cache:
        csv_dir = os.path.join(CFG_PROJECT_ROOT, _source_cfg().get("csv_dir", "data/raw"))
        path = os.path.join(csv_dir, f"{table}.csv")
        if not os.path.exists(path):
            raise RuntimeError(
                f"CSV source missing: {path}. Run 02_backend/data_generation/generate_synthetic_data.py"
            )
        _csv_cache[table] = pd.read_csv(path, low_memory=False)
    return _csv_cache[table]


def _records(df: pd.DataFrame) -> list[dict]:
    return df.to_dict("records")


# ── source accessors ───────────────────────────────────────────────────────

def list_programs() -> list[dict]:
    if data_mode() == 'pilot':
        return [providers.load()['program']]
    backend()
    return _records(_csv("programs"))


def get_program(program_id: str) -> dict | None:
    if data_mode() == 'pilot':
        return _pilot_program(program_id)
    if "@" in program_id:
        snapshot = get_snapshot(program_id)
        return snapshot["program"] if snapshot else None
    backend()
    df = _csv("programs")
    rows = _records(df[df["program_id"] == program_id])
    return rows[0] if rows else None


def list_requirements(program_id: str) -> list[dict]:
    if data_mode() == 'pilot':
        return _pilot_rows(program_id, 'requirements')
    if "@" in program_id:
        snapshot = get_snapshot(program_id)
        return snapshot["requirements"] if snapshot else []
    backend()
    df = _csv("requirements")
    return _records(df[df["program_id"] == program_id])


def list_design_specs(program_id: str) -> list[dict]:
    if data_mode() == 'pilot':
        return _pilot_rows(program_id, 'design_specs')
    if "@" in program_id:
        snapshot = get_snapshot(program_id)
        return snapshot["design_specs"] if snapshot else []
    backend()
    df = _csv("design_specs")
    return _records(df[df["program_id"] == program_id])


def list_bom(program_id: str) -> list[dict]:
    if data_mode() == 'pilot':
        return _pilot_rows(program_id, 'bom_items')
    if "@" in program_id:
        snapshot = get_snapshot(program_id)
        return snapshot["bom_items"] if snapshot else []
    backend()
    df = _csv("bom_items")
    return _records(df[df["program_id"] == program_id])


def list_test_plans(program_id: str) -> list[dict]:
    if data_mode() == 'pilot':
        return _pilot_rows(program_id, 'test_plans')
    if "@" in program_id:
        snapshot = get_snapshot(program_id)
        return snapshot["test_plans"] if snapshot else []
    backend()
    df = _csv("test_plans")
    return _records(df[df["program_id"] == program_id])


def list_suppliers() -> list[dict]:
    if data_mode() == 'pilot':
        return providers.load()['suppliers']
    backend()
    return _records(_csv('suppliers'))


def historical_requirements() -> list[dict]:
    """Requirements of non-showcase programs."""
    if data_mode() == 'pilot':
        return []
    backend()
    showcase_id = get_config().get("demo", {}).get("showcase_program_id")
    df = _csv("requirements")
    return _records(df[df["program_id"] != showcase_id])



def get_snapshot(program_id: str) -> dict | None:
    """Read a pinned snapshot. Scoped keys isolate operational records by revision."""
    if data_mode() == 'pilot':
        return providers.load() if _pilot_program(program_id) else None
    revision = program_id.partition('@')[2] or 'baseline'
    if program_id.endswith('@baseline'):
        return None
    if program_id.partition('@')[0] != 'PACK-ATLAS-01' or revision not in {'baseline','atlas-v2','atlas-v3'}:
        return None
    path = Path(CFG_PROJECT_ROOT) / _source_cfg().get('csv_dir', 'data/raw') / 'snapshots' / (revision + '.json')
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    expected = payload.pop('snapshot_id')
    actual = 'snap-' + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',',':')).encode()).hexdigest()[:16]
    if actual != expected:
        raise ValueError('Snapshot content checksum mismatch. Run prepare.py to rebuild pinned source snapshots.')
    return {**payload, 'snapshot_id':expected}


def snapshot_identity(program_id: str) -> dict:
    if data_mode() == 'pilot':
        return _pilot_identity(program_id)
    snapshot = get_snapshot(program_id)
    if '@' not in program_id:
        # Baseline CSVs remain the authoritative regression fixture.
        rows = {t:_csv(t).where(_csv(t).notna(), None).to_dict('records') for t in SOURCE_TABLES}
        rows['observations'] = snapshot['observations'] if snapshot else list_observations(program_id)
        snapshot_id = 'src-' + hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()[:16]
    else:
        snapshot_id = snapshot['snapshot_id'] if snapshot else 'legacy-csv'
    return {'program_key': program_id, 'program_id': program_id.partition('@')[0],
            'revision_id': snapshot['program']['revision_id'] if snapshot else 'baseline',
            'snapshot_id': snapshot_id}


def list_observations(program_id: str) -> list[dict]:
    if data_mode() == 'pilot':
        return _pilot_rows(program_id, 'observations')
    snapshot = get_snapshot(program_id)
    if snapshot:
        return snapshot['observations']
    if program_id.partition('@')[0]=='PACK-ATLAS-01':
        raise RuntimeError('Atlas observations are unavailable. Run 02_backend/scripts/prepare.py.')
    # Independent pinned historical measurements, separate from design features.
    centers = {'PACK-ORION-00': {'thermal':90.}, 'PACK-VEGA-00': {'thermal':92.}}
    return [{'observation_id': 'OBS-'+p['test_id'], 'test_id':p['test_id'],
             'program_id':program_id, 'measured_value':centers.get(program_id,{}).get(p['req_id'].split('-')[-1],115.),
             'unit':p['unit'], 'origin':'seeded_independent_observation'} for p in list_test_plans(program_id)]


def list_scenarios() -> list[dict]:
    if data_mode() == 'pilot':
        return []
    keys = ['PACK-ATLAS-01', 'PACK-ATLAS-01@atlas-v2', 'PACK-ATLAS-01@atlas-v3']
    return [{**snapshot_identity(key), 'label':get_snapshot(key)['program']['scenario_label']} for key in keys if get_snapshot(key)]


def _pilot_program(program_id):
    program = providers.load()['program']
    return program if program['program_id']==program_id else None


def _pilot_rows(program_id, table):
    snapshot = providers.load()
    return snapshot[table] if snapshot['program']['program_id']==program_id else []


def _pilot_identity(program_id):
    snapshot = providers.load()
    if snapshot['program']['program_id']!=program_id:
        raise providers.SourceUnavailable('Program is unavailable in the configured pilot snapshot')
    return {'program_key':program_id,'program_id':program_id,'revision_id':snapshot['revision_id'],
            'snapshot_id':snapshot['snapshot_id'],'source_id':snapshot['source_id'],
            'extracted_at':snapshot['extracted_at'],'provenance':snapshot['provenance']}

if __name__ == "__main__":
    showcase = get_config().get("demo", {}).get("showcase_program_id")
    print("backend:", backend())
    programs = list_programs()
    assert len(programs) == 3, programs
    prog = get_program(showcase)
    assert prog and prog["name"], prog
    reqs = list_requirements(showcase)
    cats = {r["category"] for r in reqs}
    assert {"range", "energy_density", "thermal", "safety", "cost"}.issubset(cats), cats
    assert list_test_plans(showcase)
    assert list_design_specs(showcase)
    assert list_bom(showcase)
    hist = historical_requirements()
    assert hist and all(r["program_id"] != showcase for r in hist)
    print(f"source OK — {len(programs)} programs, {len(reqs)} showcase reqs, {len(hist)} historical reqs")
