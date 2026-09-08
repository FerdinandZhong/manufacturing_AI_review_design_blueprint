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

import pandas as pd

from common.config import get_config, PROJECT_ROOT as CFG_PROJECT_ROOT

SOURCE_TABLES = ["programs", "requirements", "design_specs", "bom_items", "suppliers", "test_plans"]

_backend: str | None = None
_csv_cache: dict[str, pd.DataFrame] = {}


# ── backend resolution ────────────────────────────────────────────────────

def _source_cfg() -> dict:
    return get_config().get("source", {}) or {}


def backend() -> str:
    """Resolve the source backend once ('csv' for Phase 1)."""
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
    backend()
    return _records(_csv("programs"))


def get_program(program_id: str) -> dict | None:
    backend()
    df = _csv("programs")
    rows = _records(df[df["program_id"] == program_id])
    return rows[0] if rows else None


def list_requirements(program_id: str) -> list[dict]:
    backend()
    df = _csv("requirements")
    return _records(df[df["program_id"] == program_id])


def list_design_specs(program_id: str) -> list[dict]:
    backend()
    df = _csv("design_specs")
    return _records(df[df["program_id"] == program_id])


def list_bom(program_id: str) -> list[dict]:
    backend()
    df = _csv("bom_items")
    return _records(df[df["program_id"] == program_id])


def list_test_plans(program_id: str) -> list[dict]:
    backend()
    df = _csv("test_plans")
    return _records(df[df["program_id"] == program_id])


def historical_requirements() -> list[dict]:
    """Requirements of non-showcase programs."""
    backend()
    showcase_id = get_config().get("demo", {}).get("showcase_program_id")
    df = _csv("requirements")
    return _records(df[df["program_id"] != showcase_id])


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
