from agents.tools import TOOLS

def test_tools_registry_has_all():
    for name in ["get_program","list_requirements","get_traceability","get_test_results",
                 "get_design_risk","get_model_explanation","kb_search","get_asset","ontology_describe"]:
        assert name in TOOLS and callable(TOOLS[name])

def test_get_design_risk_returns_scores():
    from common.db import init_db; from engineering.test_bench import run_test_bench
    from ml.train import train
    init_db()
    for p in ["PACK-ORION-00","PACK-VEGA-00","PACK-ATLAS-01"]: run_test_bench(p)
    train()
    out = TOOLS["get_design_risk"](None, "PACK-ATLAS-01")
    assert any(x["risk_band"]=="HIGH" for x in out)
