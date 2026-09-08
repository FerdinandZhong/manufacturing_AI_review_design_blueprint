import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import source
from common.db import get_connection

REQUIRED_STANDARDS = ["UN38.3","GB 38031","IEC 62660"]

def coverage(program_id: str) -> dict:
    reqs = source.list_requirements(program_id)
    tested = {t["req_id"] for t in source.list_test_plans(program_id)}
    designed = {s["req_id"] for s in source.list_design_specs(program_id)}
    traced = [r["req_id"] for r in reqs if r["req_id"] in tested and r["req_id"] in designed]
    gaps = [r["req_id"] for r in reqs if r["req_id"] not in tested or r["req_id"] not in designed]
    total = len(reqs)
    return {"total": total, "traced": len(traced), "gaps": gaps,
            "pct": round(len(traced)/total, 3) if total else 0.0}

def build_matrix(program_id: str) -> dict:
    specs = {s["req_id"]: s["spec_id"] for s in source.list_design_specs(program_id)}
    tests = {t["req_id"]: t["test_id"] for t in source.list_test_plans(program_id)}
    conn = get_connection()
    try:
        vr = {row["test_id"]: row["verdict"] for row in
              conn.execute("SELECT test_id,verdict FROM test_results WHERE program_id=?", (program_id,))}
    finally:
        conn.close()
    rows = []
    for r in source.list_requirements(program_id):
        tid = tests.get(r["req_id"])
        rows.append({"req_id": r["req_id"], "category": r["category"],
                     "spec_id": specs.get(r["req_id"]), "test_id": tid,
                     "verdict": vr.get(tid) if tid else None})
    return {"program_id": program_id, "rows": rows}

def missing_standards(program_id: str) -> list[str]:
    have = {t.get("standard") for t in source.list_test_plans(program_id)}
    return [s for s in REQUIRED_STANDARDS if s not in have]

def decide(cov: dict, results: list[dict], missing_std: list[str]) -> str:
    verdicts = {r["verdict"] for r in results}
    if "FAIL" in verdicts or cov.get("pct", 0) < 0.6:
        return "FAIL"
    if "MARGINAL" in verdicts or cov.get("gaps") or missing_std:
        return "CONDITIONAL"
    return "PASS"

if __name__ == "__main__":
    from common.db import init_db; from engineering.test_bench import run_test_bench
    init_db(); run_test_bench("PACK-ATLAS-01")
    cov = coverage("PACK-ATLAS-01")
    assert cov["total"] >= 5
    print("traceability OK", cov, "->", decide(cov, [{"verdict":"MARGINAL"}], missing_standards("PACK-ATLAS-01")))
