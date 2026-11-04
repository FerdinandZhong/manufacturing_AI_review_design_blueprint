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

def _supplier_quality() -> dict[str, float]:
    """Read supplier quality through the shared reference-source contract."""
    return {row['supplier_id']:float(row['quality_rating']) for row in source.list_suppliers()}


def build_features(programs: list[str], require_labels: bool = True) -> pd.DataFrame:
    """Aggregate all linked designs and BOM rows; require observed labels only for training."""
    suppliers = _supplier_quality()
    rows = []
    conn = get_connection()
    try:
        for pid in programs:
            specs = source.list_design_specs(pid)
            boms = source.list_bom(pid)
            test_plans = source.list_test_plans(pid)
            verdicts = {row["test_id"]: row["verdict"] for row in conn.execute(
                "SELECT test_id, verdict FROM test_results WHERE program_id=? AND snapshot_id=?", (pid,source.snapshot_identity(pid)["snapshot_id"]))}
            for r in source.list_requirements(pid):
                req_id = r["req_id"]
                linked_tests = [t for t in test_plans if t["req_id"] == req_id]
                labels = [verdicts[t["test_id"]] for t in linked_tests if t["test_id"] in verdicts]
                if require_labels and not labels:
                    continue
                verdict = "FAIL" if "FAIL" in labels else "MARGINAL" if "MARGINAL" in labels else "PASS" if labels else None
                linked_specs = [v for v in specs if v["req_id"] == req_id]
                linked_boms = [b for b in boms if b["spec_id"] in {v["spec_id"] for v in linked_specs}]
                target_value = float(r["target_value"])
                direction = r.get("acceptance_direction", "higher")
                spec_value = (min if direction == "higher" else max)(float(v["value"]) for v in linked_specs) if linked_specs else 0.0
                margin = (spec_value - target_value) / target_value if target_value != 0 else 0.0
                margin *= 1 if direction == "higher" else -1
                bom_cost = sum(float(b["unit_cost"])*float(b["qty"]) for b in linked_boms)
                bom_mass = sum(float(b["mass_kg"])*float(b["qty"]) for b in linked_boms)
                supplier_quality = min((float(suppliers.get(b["supplier_id"], 0.0)) for b in linked_boms), default=0.0)
                rows.append({
                    "program_id": pid, "req_id": req_id,
                    "target_value": target_value, "spec_value": spec_value, "margin": margin,
                    "bom_cost": bom_cost, "bom_mass": bom_mass, "supplier_quality": supplier_quality,
                    "is_thermal": 1 if r["category"] == "thermal" else 0,
                    "is_safety": 1 if r["category"] == "safety" else 0,
                    "label": 1 if verdict in ("FAIL", "MARGINAL") else 0 if verdict else None,
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
    from common.runtime import require_demo
    require_demo('Synthetic model training')
    df = build_features(_historical_programs())
    X = df[FEATURES].to_numpy()
    y = df["label"].to_numpy()
    model = GradientBoostingClassifier(random_state=42)
    model.fit(X, y)

    model_version = "rm-" + hashlib.sha256(
        df[["program_id", "req_id"] + FEATURES + ["label"]].to_csv(index=False).encode()).hexdigest()[:10]

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
    import tempfile
    import common.db as db
    _tmp = tempfile.mkdtemp()
    db.get_db_path = lambda: os.path.join(_tmp, 'train.db')
    get_config().setdefault('ml', {})['model_dir'] = os.path.join(_tmp, 'models')
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
