import sqlite3

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS test_results (
    result_id TEXT PRIMARY KEY,
    test_id TEXT NOT NULL,
    program_id TEXT NOT NULL,
    measured_value REAL,
    verdict TEXT,                          -- PASS | MARGINAL | FAIL
    computed_by TEXT DEFAULT 'test_bench',
    run_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS design_risk_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,             -- requirement | design_spec
    entity_id TEXT NOT NULL,
    model_version TEXT,
    risk_prob REAL,
    risk_band TEXT,                        -- LOW | MEDIUM | HIGH
    top_features TEXT,                     -- json
    scored_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS gate_reviews (
    review_id TEXT PRIMARY KEY,
    program_id TEXT NOT NULL,
    state TEXT DEFAULT 'GATE_REVIEW',
    recommendation TEXT,                   -- PASS | CONDITIONAL | FAIL
    narrative TEXT,
    decided_by TEXT,
    decision TEXT,                         -- APPROVED | APPROVED_WITH_CONDITIONS | REJECTED
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    review_id TEXT REFERENCES gate_reviews(review_id),
    tool TEXT NOT NULL,
    query TEXT,
    payload_hash TEXT,
    data_version TEXT,
    agent_worker TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS annotations (
    annotation_id TEXT PRIMARY KEY,
    review_id TEXT REFERENCES gate_reviews(review_id),
    decision TEXT NOT NULL,
    rationale TEXT,
    adjudicator TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS llm_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alias TEXT UNIQUE NOT NULL,
    provider TEXT NOT NULL,
    model_identifier TEXT NOT NULL,
    api_base TEXT,
    api_key TEXT,
    is_active INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

TABLE_NAMES = ["test_results","design_risk_scores","gate_reviews","evidence","annotations","llm_models"]

def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()

if __name__ == "__main__":
    c = sqlite3.connect(":memory:"); init_schema(c)
    # ponytail: exclude sqlite's own internal sqlite_sequence table (auto-created
    # by AUTOINCREMENT columns) so this count reflects only our schema's tables.
    n = len(c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall())
    assert n == len(TABLE_NAMES), n
    print(f"schema OK — {n} tables")
