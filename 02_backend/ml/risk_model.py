"""Design-risk inference — score a program's requirements, persist to ops store.

Loads models/risk_model.pkl (training via ml/train.py if missing), scores a
program's requirements with build_features(), writes design_risk_scores rows,
and reads them back.
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "02_backend"))

import json
import pickle

from common.config import get_config
from common.db import get_connection
from ml.train import build_features, train, FEATURES, _model_dir

BANDS = [(0.66, "HIGH"), (0.33, "MEDIUM")]


def _band(risk_prob: float) -> str:
    for threshold, name in BANDS:
        if risk_prob >= threshold:
            return name
    return "LOW"


def _load_model():
    model_dir = _model_dir()
    model_path = os.path.join(model_dir, "risk_model.pkl")
    meta_path = os.path.join(model_dir, "risk_meta.json")
    if not (os.path.exists(model_path) and os.path.exists(meta_path)):
        train()
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    with open(meta_path) as f:
        meta = json.load(f)
    return model, meta


def score_program(program_id: str) -> list[dict]:
    from common.runtime import require_demo
    require_demo('Synthetic model scoring')
    model, meta = _load_model()
    df = build_features([program_id], require_labels=False)
    out = []
    conn = get_connection()
    try:
        conn.execute("DELETE FROM design_risk_scores WHERE program_id=? AND entity_type='requirement'",
                     (program_id,))
        for _, row in df.iterrows():
            X = [[row[f] for f in FEATURES]]
            risk_prob = float(model.predict_proba(X)[0][1])
            risk_band = _band(risk_prob)
            top_features = sorted(FEATURES, key=lambda f: model.feature_importances_[FEATURES.index(f)],
                                   reverse=True)[:5]
            conn.execute(
                "INSERT INTO design_risk_scores(program_id,entity_type,entity_id,model_version,"
                "risk_prob,risk_band,top_features) VALUES(?,?,?,?,?,?,?)",
                (program_id, "requirement", row["req_id"], meta["model_version"],
                 risk_prob, risk_band, json.dumps(top_features)))
            out.append({"program_id": program_id, "entity_type": "requirement",
                        "entity_id": row["req_id"], "model_version": meta["model_version"],
                        "risk_prob": risk_prob, "risk_band": risk_band,
                        "top_features": top_features})
        from common import source
        conn.execute("UPDATE design_risk_scores SET snapshot_id=? WHERE program_id=?", (source.snapshot_identity(program_id)["snapshot_id"],program_id))
        conn.commit()
    finally:
        conn.close()
    return out


def get_scores(program_id: str) -> list[dict]:
    from common.runtime import data_mode
    if data_mode()=='pilot':
        return []
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT program_id,entity_type,entity_id,model_version,risk_prob,risk_band,top_features,scored_at,snapshot_id "
            "FROM design_risk_scores WHERE program_id=? AND entity_type='requirement'", (program_id,))
        from common import source
        identity = source.snapshot_identity(program_id)
        return [dict(r) | {"top_features": json.loads(r["top_features"])} for r in rows if r["snapshot_id"] == identity["snapshot_id"]]
    finally:
        conn.close()


def explain() -> list[dict]:
    from common.runtime import data_mode
    if data_mode()=='pilot':
        return []
    model, meta = _load_model()
    order = sorted(range(len(FEATURES)), key=lambda i: model.feature_importances_[i], reverse=True)[:5]
    return [{"feature": FEATURES[i], "importance": float(model.feature_importances_[i])} for i in order]


if __name__ == "__main__":
    from common.db import init_db
    from engineering.test_bench import run_test_bench
    import tempfile
    import common.db as db
    _tmp = tempfile.mkdtemp()
    db.get_db_path = lambda: os.path.join(_tmp, 'risk.db')
    get_config().setdefault('ml', {})['model_dir'] = os.path.join(_tmp, 'models')
    init_db()
    showcase = get_config().get("demo", {}).get("showcase_program_id")
    for _p in ["PACK-ORION-00", "PACK-VEGA-00", showcase]:
        run_test_bench(_p)
    train()
    scores = score_program(showcase)
    thermal = [s for s in scores if "thermal" in s["entity_id"]]
    assert thermal and thermal[0]["risk_band"] == "HIGH", thermal
    assert get_scores(showcase)
    assert len(explain()) == 5
    print(f"risk_model OK — {len(scores)} scores, thermal risk_prob={thermal[0]['risk_prob']}")
