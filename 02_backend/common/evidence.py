import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "02_backend"))

import hashlib
import json
import uuid
from typing import Any
from common.db import get_connection


def _new_evidence_id() -> str:
    return f"EVD-{uuid.uuid4().hex[:12].upper()}"


def create_evidence(
    review_id: str,
    tool: str,
    query: str,
    payload: Any,
    data_version: str,
    agent_worker: str = "",
) -> str:
    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()
    evidence_id = _new_evidence_id()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO evidence
               (evidence_id, review_id, tool, query, payload_hash, data_version, agent_worker)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (evidence_id, review_id, tool, query, payload_hash, data_version, agent_worker),
        )
    return evidence_id


def get_evidence(evidence_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_review_evidence(review_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM evidence WHERE review_id = ? ORDER BY created_at", (review_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    import tempfile
    from common import db as db_mod

    # ponytail: override get_db_path on the db module (same mechanism db.py's own
    # self-check uses) so get_connection()/init_db() — called both here and inside
    # create_evidence/get_evidence/list_review_evidence — hit a throwaway DB, never
    # the real one. A fresh DB has zero pre-existing rows, so the ordering issue in
    # list_review_evidence (ORDER BY created_at with second-resolution timestamps)
    # can't bite: there's nothing else to tie with.
    _tmp_path = os.path.join(tempfile.mkdtemp(), "self_check.db")
    db_mod.get_db_path = lambda: _tmp_path
    db_mod.init_db()
    review_id = "GATE-SELFCHECK-01"
    with db_mod.get_connection() as _conn:
        _conn.execute(
            "INSERT OR IGNORE INTO gate_reviews (review_id, program_id) VALUES (?, ?)",
            (review_id, "PACK-SELFCHECK-00"),
        )
    eid = create_evidence(review_id, "self_check", "q", {"a": 1}, "v1", "self_check_agent")
    assert eid.startswith("EVD-")
    fetched = get_evidence(eid)
    assert fetched and fetched["review_id"] == review_id
    rows = list_review_evidence(review_id)
    assert rows and rows[0]["evidence_id"] == eid
    print(f"evidence OK — created {eid}, {len(rows)} row(s) for {review_id}, db {_tmp_path}")
