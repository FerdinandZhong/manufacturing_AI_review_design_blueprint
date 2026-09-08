"""Design-risk model training — GradientBoostingClassifier on requirement features.

Consumes source.* (requirements/design_specs/bom_items) + suppliers.csv +
ops test_results (via common/db.py). Produces build_features()/train();
saves models/risk_model.pkl + models/risk_meta.json.
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "02_backend"))

import hashlib
import json
import pickle

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier

from common import source
from common.config import get_config
from common.db import get_connection

FEATURES = ["target_value", "spec_value", "margin", "bom_cost", "bom_mass",
            "supplier_quality", "is_thermal", "is_safety"]

_suppliers_cache: dict[str, float] | None = None


def _supplier_quality() -> dict[str, float]:
    """supplier_id -> quality_rating, read directly from suppliers.csv.

    common/source.py has no list_suppliers() accessor (not in Task 2's pinned
    interfaces), so this reads the reference CSV directly — still read-only,
    still fine under the two-store rule.
    """
    global _suppliers_cache
    if _suppliers_cache is None:
        path = os.path.join(PROJECT_ROOT, "data", "raw", "suppliers.csv")
        df = pd.read_csv(path)
        _suppliers_cache = dict(zip(df["supplier_id"], df["quality_rating"]))
    return _suppliers_cache


def build_features(programs: list[str]) -> pd.DataFrame:
    """One row per requirement (that has a test result), with the 8 features + label."""
    suppliers = _supplier_quality()
    rows = []
    conn = get_connection()
    try:
        for pid in programs:
            specs = {s["req_id"]: s for s in source.list_design_specs(pid)}
            boms = {b["spec_id"]: b for b in source.list_bom(pid)}
            test_plans = {t["req_id"]: t for t in source.list_test_plans(pid)}
            verdicts = {row["test_id"]: row["verdict"] for row in conn.execute(
                "SELECT test_id, verdict FROM test_results WHERE program_id=?", (pid,))}
            for r in source.list_requirements(pid):
                req_id = r["req_id"]
                tp = test_plans.get(req_id)
                if tp is None:
                    continue  # no test plan -> can't label, exclude
                verdict = verdicts.get(tp["test_id"])
                if verdict is None:
                    continue  # not run through the test bench yet -> exclude
                spec = specs.get(req_id)
                bom = boms.get(spec["spec_id"]) if spec else None
                target_value = float(r["target_value"])
                spec_value = float(spec["value"]) if spec else 0.0
                margin = (spec_value - target_value) / target_value if target_value != 0 else 0.0
                bom_cost = float(bom["unit_cost"]) if bom else 0.0
                bom_mass = float(bom["mass_kg"]) if bom else 0.0
                supplier_quality = float(suppliers.get(bom["supplier_id"], 0.0)) if bom else 0.0
                rows.append({
                    "program_id": pid, "req_id": req_id,
                    "target_value": target_value, "spec_value": spec_value, "margin": margin,
                    "bom_cost": bom_cost, "bom_mass": bom_mass, "supplier_quality": supplier_quality,
                    "is_thermal": 1 if r["category"] == "thermal" else 0,
                    "is_safety": 1 if r["category"] == "safety" else 0,
                    "label": 1 if verdict in ("FAIL", "MARGINAL") else 0,
                })
    finally:
        conn.close()
    return pd.DataFrame(rows, columns=["program_id", "req_id"] + FEATURES + ["label"])


def _historical_programs() -> list[str]:
    showcase = get_config().get("demo", {}).get("showcase_program_id")
    return [p["program_id"] for p in source.list_programs() if p["program_id"] != showcase]


def _model_dir() -> str:
    d = get_config().get("ml", {}).get("model_dir", "models")
    return d if os.path.isabs(d) else os.path.join(PROJECT_ROOT, d)


def train() -> str:
    """Fit GradientBoostingClassifier on historical programs, persist model + meta.

    Returns the model_version string.
    """
    df = build_features(_historical_programs())
    X = df[FEATURES].to_numpy()
    y = df["label"].to_numpy()
    model = GradientBoostingClassifier(random_state=42)
    model.fit(X, y)

    model_version = "rm-" + hashlib.sha256(
        df[FEATURES].to_csv(index=False).encode()).hexdigest()[:10]

    model_dir = _model_dir()
    os.makedirs(model_dir, exist_ok=True)
    with open(os.path.join(model_dir, "risk_model.pkl"), "wb") as f:
        pickle.dump(model, f)
    with open(os.path.join(model_dir, "risk_meta.json"), "w") as f:
        json.dump({"model_version": model_version, "features": FEATURES}, f)

    return model_version


if __name__ == "__main__":
    from common.db import init_db
    from engineering.test_bench import run_test_bench
    init_db()
    for _p in _historical_programs():
        run_test_bench(_p)
    version = train()
    assert version
    hist_df = build_features(_historical_programs())
    with open(os.path.join(_model_dir(), "risk_model.pkl"), "rb") as f:
        _model = pickle.load(f)
    acc = _model.score(hist_df[FEATURES].to_numpy(), hist_df["label"].to_numpy())
    assert acc == 1.0, acc
    print(f"train OK — model_version={version}, train_acc={acc}, rows={len(hist_df)}")
