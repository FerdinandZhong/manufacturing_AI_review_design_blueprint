import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "02_backend"))

import sqlite3
from common.config import get_db_path


def get_connection() -> sqlite3.Connection:
    path = get_db_path()
    if not os.path.exists(path):
        raise RuntimeError(f"Database file not found: {path}. Run init_db() first.")
    # check_same_thread=False: FastAPI runs sync endpoints in a threadpool, so a
    # per-request connection may be used on a different worker thread than it was
    # created on. Each request still gets its own conn via get_db, so this is safe.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    from data_generation.schema import init_schema
    path = get_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    conn.close()


if __name__ == "__main__":
    import tempfile
    # ponytail: override the module-level get_db_path (looked up at call time by
    # init_db/get_connection) so this self-check hits a throwaway DB, not the real one.
    _tmp_path = os.path.join(tempfile.mkdtemp(), "self_check.db")
    get_db_path = lambda: _tmp_path
    init_db()
    conn = get_connection()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"test_results", "gate_reviews", "llm_models"} <= tables, tables
    conn.close()
    print(f"db OK — connected, {len(tables)} tables at {_tmp_path}")
