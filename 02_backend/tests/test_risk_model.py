from ml.train import train
from ml.risk_model import score_program, get_scores, explain
from common.db import init_db
from engineering.test_bench import run_test_bench

def test_train_and_score_thermal_high_and_deterministic():
    init_db()
    for p in ["PACK-ORION-00","PACK-VEGA-00","PACK-ATLAS-01"]:
        run_test_bench(p)
    v = train()
    assert v
    s1 = score_program("PACK-ATLAS-01")
    s2 = score_program("PACK-ATLAS-01")
    assert [(x["entity_id"],x["risk_band"]) for x in s1] == [(x["entity_id"],x["risk_band"]) for x in s2]
    thermal = [x for x in s1 if "thermal" in x["entity_id"]]
    assert thermal and thermal[0]["risk_band"] == "HIGH"
    assert len(explain()) == 5
