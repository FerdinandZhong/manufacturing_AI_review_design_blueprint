from common.db import init_db
from engineering.test_bench import run_test_bench

def test_bench_is_deterministic_and_thermal_is_marginal(tmp_path, monkeypatch):
    init_db()
    r1 = run_test_bench("PACK-ATLAS-01")
    r2 = run_test_bench("PACK-ATLAS-01")
    assert [ (x["test_id"],x["measured_value"],x["verdict"]) for x in r1 ] == \
           [ (x["test_id"],x["measured_value"],x["verdict"]) for x in r2 ]
    verdicts = {x["test_id"]: x["verdict"] for x in r1}
    assert "MARGINAL" in verdicts.values()
    # the thermal test is the marginal one
    thermal = [x for x in r1 if x["test_id"].startswith("T-ATLAS-thermal")]
    assert thermal and thermal[0]["verdict"] == "MARGINAL"
