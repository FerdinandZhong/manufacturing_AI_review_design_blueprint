import sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import source
from common.db import get_connection

# per-category deterministic transform: measured = spec_value * FACTOR[category]
FACTOR = {"range":1.0,"energy_density":1.0,"thermal":1.0,"safety":1.0,"cost":1.0}

def _verdict(measured: float, target: float) -> str:
    if target == 0: return "PASS"
    margin = (measured - target) / target
    if margin >= 0.10: return "PASS"
    if margin >= 0.0:  return "MARGINAL"
    return "FAIL"

def run_test_bench(program_id: str) -> list[dict]:
    specs = {s["req_id"]: s for s in source.list_design_specs(program_id)}
    out = []
    conn = get_connection()
    try:
        conn.execute("DELETE FROM test_results WHERE program_id=?", (program_id,))
        for tp in source.list_test_plans(program_id):
            spec = specs.get(tp["req_id"])
            base = float(spec["value"]) if spec else 0.0
            cat = tp.get("standard","")  # category proxy; real category via req lookup below
            # measured derived deterministically from design spec value
            measured = round(base * FACTOR.get(_category(program_id, tp["req_id"]), 1.0), 4)
            target = float(tp["target_value"])
            v = _verdict(measured, target)
            rid = f"R-{uuid.uuid5(uuid.NAMESPACE_OID, tp['test_id']).hex[:10]}"
            conn.execute(
                "INSERT INTO test_results(result_id,test_id,program_id,measured_value,verdict) VALUES(?,?,?,?,?)",
                (rid, tp["test_id"], program_id, measured, v))
            out.append({"result_id":rid,"test_id":tp["test_id"],"program_id":program_id,
                        "measured_value":measured,"verdict":v})
        conn.commit()
    finally:
        conn.close()
    return out

_REQ_CAT = {}
def _category(program_id: str, req_id: str) -> str:
    if program_id not in _REQ_CAT:
        _REQ_CAT[program_id] = {r["req_id"]: r["category"] for r in source.list_requirements(program_id)}
    return _REQ_CAT[program_id].get(req_id, "")

if __name__ == "__main__":
    from common.db import init_db; init_db()
    r = run_test_bench("PACK-ATLAS-01")
    assert any(x["verdict"]=="MARGINAL" for x in r), r
    print(f"test_bench OK — {len(r)} results, verdicts={[x['verdict'] for x in r]}")
