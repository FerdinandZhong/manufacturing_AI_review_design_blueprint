"""One idempotent bootstrap: init_db -> test bench (all programs) -> train ->
build_kb -> summary. The AMP calls this as a single "Prepare Data, Model & KB"
task; local dev calls it the same way. Safe to re-run (init_db is CREATE IF
NOT EXISTS, run_test_bench DELETEs+re-inserts per program, train/build_kb
overwrite their artifacts).
"""
import sys
import os
from collections import Counter

# scripts/ is one level under 02_backend/, same depth as engineering/ml/knowledge
# -> one level up from this file reaches 02_backend.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "02_backend"))

from common import source
from common.config import get_config
from common.db import init_db, get_connection
from engineering.test_bench import run_test_bench
from ml.train import train
from ml.risk_model import score_program
from knowledge.kb import build_kb


def main() -> None:
    init_db()

    programs = [p["program_id"] for p in source.list_programs()]
    results = []
    for pid in programs:
        results.extend(run_test_bench(pid))

    model_version = train()

    showcase = get_config().get("demo", {}).get("showcase_program_id")
    scores = score_program(showcase)

    kb_rows = build_kb()

    verdicts = Counter(r["verdict"] for r in results)
    thermal = [s for s in scores if "thermal" in s["entity_id"]]
    assert thermal, f"no thermal requirement scored for {showcase}"

    thermal_result = next(
        (r for r in results if r["program_id"] == showcase and "thermal" in r["test_id"].lower()),
        None,
    )

    print("=" * 55)
    print("Vehicle NPI Blueprint — bootstrap summary")
    print("=" * 55)
    print(f"Programs:        {len(programs)} ({', '.join(programs)})")
    print(f"Test results:    {len(results)} — {dict(verdicts)}")
    print(f"Model version:   {model_version}")
    print(f"Risk scores:     {len(scores)} (showcase={showcase})")
    print(f"KB assets:       {kb_rows}")
    print(f"Thermal risk:    band={thermal[0]['risk_band']} prob={thermal[0]['risk_prob']:.3f}")

    # Demo-critical invariants (this script IS the smoke test — running it is the check).
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT verdict FROM test_results WHERE program_id=? AND test_id LIKE '%thermal%'",
            (showcase,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, f"no thermal test result found for {showcase}"
    assert row["verdict"] == "MARGINAL", f"expected showcase thermal verdict MARGINAL, got {row['verdict']}"
    assert thermal[0]["risk_band"] == "HIGH", f"expected showcase thermal risk_band HIGH, got {thermal[0]['risk_band']}"

    print()
    print("Invariants OK — thermal test MARGINAL, thermal risk HIGH.")


if __name__ == "__main__":
    main()
