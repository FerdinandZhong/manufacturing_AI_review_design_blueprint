import sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import source
from common.db import get_connection

def _verdict(measured: float, target: float, direction: str = "higher") -> str:
    if target == 0: return "PASS"
    if direction not in {"higher", "lower"}:
        raise ValueError("Acceptance direction must be higher or lower")
    margin = (measured - target) / abs(target) * (1 if direction == "higher" else -1)
    if margin >= 0.10: return "PASS"
    if margin >= 0.0:  return "MARGINAL"
    return "FAIL"

def run_test_bench(program_id: str) -> list[dict]:
    from common.runtime import require_demo
    require_demo('Synthetic test bench')
    observations = source.list_observations(program_id)
    out = []
    conn = get_connection()
    try:
        conn.execute("DELETE FROM test_results WHERE program_id=?", (program_id,))
        for tp in source.list_test_plans(program_id):
            samples = [o for o in observations if o['test_id'] == tp['test_id']]
            if not samples:
                raise ValueError(f"No observations for {tp['test_id']}")
            if any(o['unit'] != tp['unit'] for o in samples):
                raise ValueError(f"Observation unit mismatch for {tp['test_id']}")
            measured = round(sum(float(o['measured_value']) for o in samples) / len(samples), 4)
            target = float(tp['target_value'])
            direction = tp.get('acceptance_direction', 'higher')
            v = _verdict(measured, target, direction)
            rid = f"R-{uuid.uuid5(uuid.NAMESPACE_OID, program_id + ':' + tp['test_id']).hex[:10]}"
            conn.execute(
                "INSERT INTO test_results(result_id,test_id,program_id,measured_value,verdict) VALUES(?,?,?,?,?)",
                (rid, tp["test_id"], program_id, measured, v))
            out.append({"result_id":rid,"test_id":tp["test_id"],"program_id":program_id,
                        "measured_value":measured,"verdict":v})
        conn.execute("UPDATE test_results SET snapshot_id=? WHERE program_id=?", (source.snapshot_identity(program_id)["snapshot_id"],program_id))
        conn.commit()
    finally:
        conn.close()
    return out

if __name__ == "__main__":
    import tempfile
    import common.db as db
    db.get_db_path = lambda: os.path.join(_tmp, "bench.db")
    _tmp = tempfile.mkdtemp()
    from common.db import init_db; init_db()
    r = run_test_bench("PACK-ATLAS-01")
    assert any(x["verdict"]=="MARGINAL" for x in r), r
    print(f"test_bench OK — {len(r)} results, verdicts={[x['verdict'] for x in r]}")
