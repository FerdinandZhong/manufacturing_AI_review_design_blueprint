"""Supervisor: dispatch the 5 gate-review workers in parallel, compute the
code-decided recommendation, stream a narrative, and persist the gate_reviews
row. Mirrors AML's agents/supervisor.py structure, adapted for our linear
REQUIREMENTS->...->GATE_REVIEW->RELEASED state machine (no VERIFYING phase —
we have no MCP verification worker).

Event shapes emitted:
  {"type": "phase",          "phase": str}
  {"type": "worker_start",   "worker": str}
  {"type": "worker_done",    "worker": str, "findings": str, "evidence_ids": [str]}
  {"type": "recommendation", "value": str}
  {"type": "token",          "text": str}
  {"type": "done"}

Code decides, LLM narrates: the recommendation comes from
engineering.traceability.decide() — a pure function over already-computed
deterministic data (coverage/test_results/missing_standards). Worker LLM
calls and narrate() affect only prose, never this value.

Two-store rule: the one legitimate mutation here is the gate_reviews row
(ops store) — everything else workers touch is read-only.
"""
import sys
import os
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "02_backend"))

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Generator

from agents.state_machine import ProgramState, transition
from agents.workers import (
    run_coverage_worker, run_testverdict_worker, run_compliance_worker,
    run_designrisk_worker, run_knowledgereuse_worker,
)
from agents.narrative import narrate
from common.db import get_connection
from engineering.traceability import coverage, decide, missing_standards
from agents.tools import TOOLS


def _e(type_: str, **kw) -> dict:
    return {"type": type_, **kw}


_WORKERS = [
    ("coverage", run_coverage_worker),
    ("testverdict", run_testverdict_worker),
    ("compliance", run_compliance_worker),
    ("designrisk", run_designrisk_worker),
    ("knowledgereuse", run_knowledgereuse_worker),
]


def run_gate_review(review_id: str, program_id: str) -> Generator[dict, None, None]:
    # The plan's showcase program is pre-seeded through VALIDATION; this call
    # exercises the final GATE_REVIEW -> RELEASED leg of the state machine.
    state = transition(ProgramState.VALIDATION, ProgramState.GATE_REVIEW)

    # Seed the gate_reviews row now (state=GATE_REVIEW, default) so the FK
    # from evidence.review_id -> gate_reviews.review_id is satisfiable before
    # any worker below calls create_evidence. Finalized with an UPDATE once
    # the recommendation + narrative are known.
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO gate_reviews (review_id, program_id, state, execution_status) VALUES (?, ?, ?, 'running')",
            (review_id, program_id, state.value),
        )

    yield _e("phase", phase="COLLECTING")
    findings_list = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {}
        for name, fn in _WORKERS:
            yield _e("worker_start", worker=name)
            futures[ex.submit(fn, review_id, program_id)] = name
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                result = fut.result()
            except Exception as exc:
                result = {"worker": name, "findings": f"Error: {exc}", "evidence_ids": []}
            findings_list.append(result)
    # Deterministic emission order regardless of thread completion order, so
    # the SSE event sequence (beyond timing) is stable across runs.
    findings_list.sort(key=lambda r: r["worker"])
    for result in findings_list:
        yield _e("worker_done", worker=result["worker"], findings=result["findings"], evidence_ids=result["evidence_ids"])

    # Code decides: pure function over already-deterministic data — never
    # influenced by any worker's LLM-generated prose.
    cov = coverage(program_id)
    test_results = TOOLS["get_test_results"](None, program_id)
    missing_std = missing_standards(program_id)
    rec = decide(cov, test_results, missing_std)
    yield _e("recommendation", value=rec)

    yield _e("phase", phase="ANALYZING")
    narrative_chunks = []
    for tok in narrate(program_id, findings_list, rec):
        narrative_chunks.append(tok)
        yield _e("token", text=tok)
    narrative_text = "".join(narrative_chunks)

    with get_connection() as conn:
        conn.execute(
            "UPDATE gate_reviews SET recommendation=?, narrative=?, worker_results=?, "
            "execution_status='completed', execution_error=NULL, completed_at=datetime('now') WHERE review_id=?",
            (rec, narrative_text, json.dumps(findings_list, sort_keys=True), review_id),
        )

    transition(state, ProgramState.RELEASED)
    yield _e("done")


if __name__ == "__main__":
    from common.db import init_db
    from engineering.test_bench import run_test_bench
    from ml.train import train
    from knowledge.kb import build_kb

    import tempfile
    import common.db as db
    _tmp = tempfile.mkdtemp()
    db.get_db_path = lambda: os.path.join(_tmp, "self_check.db")
    init_db()
    for _p in ["PACK-ORION-00", "PACK-VEGA-00", "PACK-ATLAS-01"]:
        run_test_bench(_p)
    train()
    from ml.risk_model import score_program
    score_program("PACK-ATLAS-01")
    build_kb()

    events = list(run_gate_review("REV-SUPERVISOR-SELFCHECK", "PACK-ATLAS-01"))
    types = [e["type"] for e in events]
    assert types[-1] == "done", types
    assert "recommendation" in types, types
    recs = [e["value"] for e in events if e["type"] == "recommendation"]
    assert recs == ["CONDITIONAL"], recs
    workers = {e["worker"] for e in events if e["type"] == "worker_done"}
    assert workers == {"coverage", "testverdict", "compliance", "designrisk", "knowledgereuse"}, workers

    with get_connection() as conn:
        row = conn.execute(
            "SELECT recommendation, narrative FROM gate_reviews WHERE review_id=?",
            ("REV-SUPERVISOR-SELFCHECK",),
        ).fetchone()
    assert row and row["recommendation"] == "CONDITIONAL" and row["narrative"], dict(row) if row else None

    print(f"supervisor OK — {len(events)} events, recommendation={recs[0]}, workers={sorted(workers)}")
