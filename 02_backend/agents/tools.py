"""Agent tool registry — thin, read-only wrappers over source/traceability/ops/
risk_model/kb/ontology, keyed by tool name for LLM agent function-calling.

Two-store rule: every wrapper here only reads (source CSV, ops SQLite,
Lance KB, ontology YAML). The one legitimate write in this task's scope is
common/evidence.py's create_evidence, not this module.

Signature convention: fn(conn, *args) mirroring AML — conn may be None; tools
that need DB access and get conn=None open their own short-lived connection
via common.db.get_connection() and close it (matching engineering/traceability.py).
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "02_backend"))

from common import source
from common.db import get_connection
from engineering import traceability
from ml import risk_model
from knowledge import kb, ontology


def get_program(conn, program_id):
    return source.get_program(program_id)


def list_requirements(conn, program_id):
    return source.list_requirements(program_id)


def get_traceability(conn, program_id):
    return traceability.build_matrix(program_id)


def get_test_results(conn, program_id):
    own = conn is None
    c = get_connection() if own else conn
    try:
        rows = c.execute("SELECT * FROM test_results WHERE program_id=?", (program_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own:
            c.close()


def get_design_risk(conn, program_id):
    return risk_model.get_scores(program_id)


def get_model_explanation(conn, *args):
    return risk_model.explain()


def kb_search(conn, query, ontology_filter=None, k=3):
    return kb.search(query, ontology_filter, k)


def get_asset(conn, asset_id):
    return kb.get_asset(asset_id)


def ontology_describe(conn, cls):
    return ontology.describe(cls)


TOOLS = {
    "get_program": get_program,
    "list_requirements": list_requirements,
    "get_traceability": get_traceability,
    "get_test_results": get_test_results,
    "get_design_risk": get_design_risk,
    "get_model_explanation": get_model_explanation,
    "kb_search": kb_search,
    "get_asset": get_asset,
    "ontology_describe": ontology_describe,
}


if __name__ == "__main__":
    from common.config import get_config
    showcase = get_config().get("demo", {}).get("showcase_program_id")

    assert set(TOOLS) == {
        "get_program", "list_requirements", "get_traceability", "get_test_results",
        "get_design_risk", "get_model_explanation", "kb_search", "get_asset", "ontology_describe",
    }
    assert all(callable(fn) for fn in TOOLS.values())

    prog = TOOLS["get_program"](None, showcase)
    assert prog and prog["program_id"] == showcase, prog

    reqs = TOOLS["list_requirements"](None, showcase)
    assert reqs, reqs

    matrix = TOOLS["get_traceability"](None, showcase)
    assert matrix["program_id"] == showcase and matrix["rows"], matrix

    results = TOOLS["get_test_results"](None, showcase)
    assert isinstance(results, list)

    exp = TOOLS["get_model_explanation"](None)
    assert len(exp) == 5, exp

    cls = ontology.classes()[0]
    desc = TOOLS["ontology_describe"](None, cls)
    assert isinstance(desc, dict), desc

    print(f"tools OK — {len(TOOLS)} registered, showcase={showcase}, "
          f"{len(reqs)} reqs, {len(matrix['rows'])} traceability rows")
