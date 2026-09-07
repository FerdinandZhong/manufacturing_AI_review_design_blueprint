import sqlite3
from data_generation.schema import init_schema, TABLE_NAMES

def test_schema_creates_all_ops_tables():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    got = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert set(TABLE_NAMES).issubset(got)
    assert {"test_results","design_risk_scores","gate_reviews","evidence","annotations","llm_models"}.issubset(got)
