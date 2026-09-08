from agents.supervisor import run_gate_review
from common.db import init_db
from engineering.test_bench import run_test_bench
from ml.train import train
from knowledge.kb import build_kb


def test_gate_review_deterministic_recommendation_and_evidence():
    init_db()
    for p in ["PACK-ORION-00", "PACK-VEGA-00", "PACK-ATLAS-01"]:
        run_test_bench(p)
    train()
    build_kb()

    def rec(events):
        types = [e["type"] for e in events]
        r = [e["value"] for e in events if e["type"] == "recommendation"][0]
        workers = [e["worker"] for e in events if e["type"] == "worker_done"]
        return types, r, workers

    e1 = list(run_gate_review("REV-1", "PACK-ATLAS-01"))
    e2 = list(run_gate_review("REV-2", "PACK-ATLAS-01"))
    t1, r1, w1 = rec(e1)
    t2, r2, w2 = rec(e2)
    assert r1 == r2 == "CONDITIONAL"
    assert set(w1) == {"coverage", "testverdict", "compliance", "designrisk", "knowledgereuse"}
    assert e1[-1]["type"] == "done"
