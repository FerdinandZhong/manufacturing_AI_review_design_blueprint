import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import source
from common.runtime import data_mode
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
    specs = source.list_design_specs(program_id)
    tests = source.list_test_plans(program_id)
    pilot = data_mode()=='pilot'
    vr = {}
    if not pilot:
        conn = get_connection()
        try:
            vr = {row['test_id']: row['verdict'] for row in conn.execute(
                'SELECT test_id,verdict FROM test_results WHERE program_id=? AND snapshot_id=?',
                (program_id,source.snapshot_identity(program_id)['snapshot_id']))}
        finally:
            conn.close()
    rows = []
    for r in source.list_requirements(program_id):
        spec_ids = [v['spec_id'] for v in specs if v['req_id'] == r['req_id']]
        test_ids = [v['test_id'] for v in tests if v['req_id'] == r['req_id']]
        verdicts = [vr[t] for t in test_ids if t in vr]
        worst = max(verdicts, key={'PASS':0,'MARGINAL':1,'FAIL':2}.get) if verdicts else None
        rows.append({'req_id':r['req_id'], 'category':r['category'],
                     'spec_id':spec_ids[0] if spec_ids else None,
                     'test_id':test_ids[0] if test_ids else None,
                     'spec_ids':spec_ids, 'test_ids':test_ids, 'verdict':worst})
    if pilot:
        return {'program_id':program_id,'rows':rows,'status':'structural_only','verdict_status':'unavailable_pending_approved_pilot_rules'}
    return {"program_id": program_id, "rows": rows}

def missing_standards(program_id: str) -> list[str] | None:
    if data_mode()=='pilot':
        return None
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
    import tempfile
    import common.db as db
    _tmp = tempfile.mkdtemp()
    db.get_db_path = lambda: os.path.join(_tmp, "trace.db")
    init_db(); run_test_bench("PACK-ATLAS-01")
    cov = coverage("PACK-ATLAS-01")
    assert cov["total"] >= 5
    print("traceability OK", cov, "->", decide(cov, [{"verdict":"MARGINAL"}], missing_standards("PACK-ATLAS-01")))
