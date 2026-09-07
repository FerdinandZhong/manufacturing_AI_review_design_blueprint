# Phase 1 — Walking Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Workbench-deployable, deterministic agentic demo: an EV battery-pack NPI program at its release gate, where a traditional ML risk model + a multimodal Lance knowledge base feed an agent "Gate Review" that streams findings and yields a code-computed PASS/CONDITIONAL/FAIL, with a human decision.

**Architecture:** Mirror `../anti_money_laundry_blueprint` (AML). Three stores: **CSV source** (read-only reference via `common/source.py`, `backend: auto|iceberg|csv` — csv only in Phase 1), **SQLite ops** (`data/npi.db`, runtime state), **Lance** (`data/kb/assets.lance`, multimodal assets + ontology). Deterministic core (test-bench, traceability, ML inference on a saved seeded model, precomputed embeddings) produces all numbers/decisions; LLM agents only narrate, with a template fallback. Backend FastAPI (SSE for gate review), frontend React 19 + Vite + Tailwind (Dashboard A only).

**Tech Stack:** Python 3.11 · FastAPI · Uvicorn · pandas · numpy · scikit-learn · pylance (Lance) · pyyaml · openai (OpenAI-compatible client) · React 19 · Vite · Tailwind.

## Global Constraints

- **Python 3.11**; all backend modules import via `sys.path.insert(0, .../02_backend)` exactly as AML does.
- **Determinism is sacred.** Every generator/computation uses a fixed seed `SEED = 42`. No `Date.now()`/`random()` without seeding. `test_bench`, `traceability.decide()`, and `risk_model` inference must be byte-identical across runs. LLM affects **prose only**.
- **Code decides, LLM narrates.** The gate recommendation is `traceability.decide(...)` (pure function). `narrate()` wraps findings in prose via LLM; on any LLM error/timeout it returns a deterministic template string. The demo never hard-fails on LLM.
- **Two-store rule:** source/reference data is read-only via `common/source.py` (never written by the app); all runtime writes go to SQLite ops (`common/db.py`) or are Lance build-time only.
- **Ports:** backend `BACKEND_PORT=7078`, frontend `CDSW_APP_PORT` (fallback `8100`). Copy AML `start_app.py` verbatim.
- **Showcase program id:** `PACK-ATLAS-01`. Historical programs: `PACK-ORION-00`, `PACK-VEGA-00`. The thermal requirement of the showcase must score ML **HIGH** and its thermal test must be **MARGINAL** — this corroboration is the demo's spine; tests assert it.
- **LLM provider** via `config/config.yaml` (`caii|vllm|ollama`), OpenAI-compatible, `temperature=0.1` (copy AML `llm_client.py` + `common/caii.py`).
- **Copy-from-AML files (verbatim unless noted), from `../anti_money_laundry_blueprint/02_backend/`:** `common/config.py` (change default db to `data/npi.db`), `common/caii.py`, `agents/llm_client.py`. Copy `common/db.py`, `common/evidence.py`, `agents/state_machine.py` with the renames specified in their tasks. Copy `start_app.py`, `01_installer/install.py`, and the `03_frontend/` scaffold.
- **Every Python module ends with a `if __name__ == "__main__":` assert-based self-check** (AML convention). Tests live in `02_backend/tests/`.
- **Commit after every task** with a `feat:`/`test:` message.

---

## Interfaces (pinned once; every task must match these signatures)

```
# common/source.py    (backend: auto|iceberg|csv — csv implemented)
backend() -> str
list_programs() -> list[dict]
get_program(program_id: str) -> dict | None
list_requirements(program_id: str) -> list[dict]
list_design_specs(program_id: str) -> list[dict]
list_bom(program_id: str) -> list[dict]
list_test_plans(program_id: str) -> list[dict]
historical_requirements() -> list[dict]          # requirements of non-showcase programs

# common/db.py        (copy AML; ops store)
get_connection() -> sqlite3.Connection
init_db() -> None

# common/evidence.py  (copy AML; rename case_id -> review_id)
create_evidence(review_id: str, tool: str, query: str, payload, data_version: str, agent_worker: str = "") -> str
list_review_evidence(review_id: str) -> list[dict]

# engineering/test_bench.py
run_test_bench(program_id: str) -> list[dict]     # computes + writes test_results rows; returns them

# engineering/traceability.py
coverage(program_id: str) -> dict                 # {"total":int,"traced":int,"gaps":[req_id,...],"pct":float}
build_matrix(program_id: str) -> dict             # {"rows":[{req_id,category,spec_id,test_id,verdict}], ...}
missing_standards(program_id: str) -> list[str]   # required standards not covered by any test_plan
decide(cov: dict, results: list[dict], missing_std: list[str]) -> str   # "PASS"|"CONDITIONAL"|"FAIL"

# ml/train.py
build_features(programs: list[str]) -> "pd.DataFrame"     # one row per requirement, numeric features + label
train() -> str                                            # trains, saves model+meta to models/, returns model_version

# ml/risk_model.py
score_program(program_id: str) -> list[dict]      # writes design_risk_scores; returns [{entity_id,risk_prob,risk_band,top_features}]
get_scores(program_id: str) -> list[dict]
explain() -> list[dict]                           # [{"feature":str,"importance":float}] top-5

# knowledge/ontology.py
load_ontology() -> dict
classes() -> list[str]
relations() -> list[dict]                         # [{"from":cls,"rel":str,"to":cls}]
describe(cls: str) -> dict
validate_asset(asset: dict) -> bool               # asset["ontology_class"] in classes()

# knowledge/kb.py
embed(text: str) -> list[float]                   # precomputed model or hashing fallback; deterministic
build_kb() -> int                                 # (re)builds assets.lance; returns row count
search(query: str, ontology_filter: str | None = None, k: int = 3) -> list[dict]   # [{asset_id,ontology_class,title,score,linked_entity_id,...}]
get_asset(asset_id: str) -> dict                  # includes "blob" (bytes) + "modality"

# agents/state_machine.py  (copy AML; new enum)
class ProgramState(str,Enum): REQUIREMENTS, DESIGN, ENGINEERING, VALIDATION, GATE_REVIEW, RELEASED
transition(current, next) -> ProgramState

# agents/workers.py   (each returns {"worker":str,"findings":str,"evidence_ids":[str]})
run_coverage_worker(review_id, program_id) -> dict
run_testverdict_worker(review_id, program_id) -> dict
run_compliance_worker(review_id, program_id) -> dict
run_designrisk_worker(review_id, program_id) -> dict
run_knowledgereuse_worker(review_id, program_id) -> dict

# agents/supervisor.py
run_gate_review(review_id: str, program_id: str) -> "Generator[dict,None,None]"   # yields event dicts
# event shapes (AML): {"type":"phase","phase":str} {"type":"worker_start","worker":str}
#   {"type":"worker_done","worker":str,"findings":str,"evidence_ids":[str]}
#   {"type":"recommendation","value":str}  {"type":"token","text":str}  {"type":"done"}

# agents/narrative.py
narrate(program_id: str, findings: list[dict], recommendation: str) -> "Iterator[str]"   # LLM stream OR yields one template string
```

---

## Task 0: Repo scaffold + copy AML plumbing

**Files:**
- Create: `02_backend/__init__.py`, `02_backend/{common,agents,engineering,ml,knowledge,api,data_generation,tests}/__init__.py`
- Create (copy from AML): `02_backend/common/config.py`, `common/caii.py`, `agents/llm_client.py`, `start_app.py`, `01_installer/install.py`
- Create: `config/config.yaml.example`, `config/config.yaml`, `requirements.txt`, `.gitignore`
- Create: `data/`, `models/`, `data/raw/`, `data/kb/raw/` (empty, gitkept)

**Interfaces:** Produces `get_config()`, `get_db_path()`, `PROJECT_ROOT`, `chat()` for all later tasks.

- [ ] **Step 1:** Copy `../anti_money_laundry_blueprint/02_backend/common/config.py` → `02_backend/common/config.py`. Change the db default: `raw = cfg.get("data", {}).get("db_path", "data/npi.db")`.
- [ ] **Step 2:** Copy `common/caii.py` and `agents/llm_client.py` verbatim from AML.
- [ ] **Step 3:** Copy `start_app.py` and `01_installer/install.py` from AML; change the `data/aml.db` prereq check to `data/npi.db` and the printed app name to "Vehicle NPI Blueprint".
- [ ] **Step 4:** Write `requirements.txt`:

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
pydantic>=2.0.0
httpx>=0.27.0
pyyaml>=6.0
openai>=1.0.0
pandas>=2.1.0
numpy>=1.26.0
scikit-learn>=1.4.0
pylance>=0.13.0
python-dotenv>=1.0.0
```

- [ ] **Step 5:** Write `config/config.yaml.example` (llm block copied from AML; add):

```yaml
data:
  db_path: data/npi.db      # ops store
  raw_dir: data/raw         # csv source fallback
  kb_dir: data/kb           # lance dataset + raw assets
source:
  backend: auto             # auto | iceberg | csv  (Phase 1: csv)
  csv_dir: data/raw
demo:
  showcase_program_id: PACK-ATLAS-01
ml:
  model_dir: models
  seed: 42
```

  Then `cp config/config.yaml.example config/config.yaml`.
- [ ] **Step 6:** Write `.gitignore` (`data/*.db*`, `data/kb/*.lance`, `models/*.pkl`, `__pycache__/`, `node_modules/`, `.env`).
- [ ] **Step 7:** Verify config loads.

Run: `cd 02_backend && python -c "from common.config import get_config,get_db_path; print(get_db_path())"`
Expected: prints an absolute path ending `data/npi.db`.

- [ ] **Step 8:** Commit. `git init` if needed; `git add -A && git commit -m "chore: scaffold + AML plumbing"`.

---

## Task 1: Ops schema (SQLite)

**Files:**
- Create: `02_backend/data_generation/schema.py`
- Create: `02_backend/common/db.py` (copy AML, renames below)
- Test: `02_backend/tests/test_schema.py`

**Interfaces:** Consumes nothing. Produces `init_db()`, `get_connection()`, ops tables.

- [ ] **Step 1: Write the failing test** `tests/test_schema.py`:

```python
import sqlite3
from data_generation.schema import init_schema, TABLE_NAMES

def test_schema_creates_all_ops_tables():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    got = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert set(TABLE_NAMES).issubset(got)
    assert {"test_results","design_risk_scores","gate_reviews","evidence","annotations","llm_models"}.issubset(got)
```

- [ ] **Step 2: Run to verify it fails.** Run: `cd 02_backend && python -m pytest tests/test_schema.py -v` → FAIL (module not found).
- [ ] **Step 3: Write `data_generation/schema.py`:**

```python
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
    n = len(c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
    assert n == len(TABLE_NAMES), n
    print(f"schema OK — {n} tables")
```

- [ ] **Step 4:** Copy AML `common/db.py` → `02_backend/common/db.py`. Remove AML's ALTER/heal block; keep `get_connection()` (WAL, `row_factory=Row`, `check_same_thread=False`) and `init_db()` calling `from data_generation.schema import init_schema`.
- [ ] **Step 5: Run tests.** `python -m pytest tests/test_schema.py -v` and `python data_generation/schema.py` → PASS / "schema OK — 6 tables".
- [ ] **Step 6: Commit.** `git add -A && git commit -m "feat: sqlite ops schema"`.

---

## Task 2: Synthetic source data (CSV) + source layer

**Files:**
- Create: `02_backend/data_generation/generate_synthetic_data.py`
- Create: `02_backend/common/source.py`
- Test: `02_backend/tests/test_source.py`

**Interfaces:** Produces the `source.py` accessors listed in Interfaces. Consumes `get_config`.

**Data contract (CSV columns under `data/raw/`):**
- `programs.csv`: `program_id,name,vehicle_platform,target_market,stage,gate_status`
- `requirements.csv`: `req_id,program_id,category,text,target_value,unit,priority,source,status`  (category ∈ range|energy_density|thermal|safety|cost)
- `design_specs.csv`: `spec_id,program_id,req_id,parameter,value,unit,rationale,cell_chemistry,version`
- `bom_items.csv`: `part_id,program_id,spec_id,name,supplier_id,qty,unit_cost,mass_kg`
- `suppliers.csv`: `supplier_id,name,region,quality_rating`
- `test_plans.csv`: `test_id,program_id,req_id,method,standard,pass_criteria,target_value,unit`

**Seeding intent (must hold for downstream asserts):** 3 programs. Each has 5 requirements (one per category). For the **showcase** `PACK-ATLAS-01`, the `thermal` design spec is set so its test-bench margin is ~+3% → **MARGINAL**, and its feature vector matches the historical failure pattern → ML **HIGH**. Historical `PACK-ORION-00` has a thermal requirement whose recorded outcome was a failure (label=1) with a linked design image + test report asset (Task 7). One requirement in the showcase is intentionally left with **no test_plan** → a coverage gap.

- [ ] **Step 1: Write the failing test** `tests/test_source.py`:

```python
from common import source

def test_showcase_program_and_children_present():
    p = source.get_program("PACK-ATLAS-01")
    assert p and p["name"]
    reqs = source.list_requirements("PACK-ATLAS-01")
    cats = {r["category"] for r in reqs}
    assert {"range","energy_density","thermal","safety","cost"}.issubset(cats)
    assert any(r["req_id"] for r in reqs)
    assert source.list_test_plans("PACK-ATLAS-01")            # has some tests
    assert source.list_design_specs("PACK-ATLAS-01")
    assert len(source.list_programs()) == 3
    assert source.historical_requirements()                   # non-showcase reqs exist

def test_one_requirement_has_no_test_plan():
    reqs = {r["req_id"] for r in source.list_requirements("PACK-ATLAS-01")}
    tested = {t["req_id"] for t in source.list_test_plans("PACK-ATLAS-01")}
    assert reqs - tested, "expected at least one uncovered requirement (coverage gap)"
```

- [ ] **Step 2: Run to verify it fails.** `python -m pytest tests/test_source.py -v` → FAIL.
- [ ] **Step 3: Write `generate_synthetic_data.py`** — deterministic (`random.seed(42)`), builds the 6 DataFrames per the contract/seeding intent, writes CSVs to `data/raw/`. Use explicit literal rows for the showcase program (so thermal values are pinned); generate historical programs from a small loop with fixed per-category base values + a fixed offset per program. Include the thermal spec value that yields ~+3% margin (Task 3 formula). Leave the `cost` requirement of the showcase without a `test_plans` row. End with a self-check asserting row counts and that re-running produces identical CSV bytes (hash compare).

- [ ] **Step 4: Write `common/source.py`** — adapt AML's structure: `backend()` resolves `auto|iceberg|csv`; `iceberg` raises `RuntimeError("iceberg backend not configured (Phase 1 is csv)")`; `csv` reads `data/raw/*.csv` via pandas with a per-process cache. Implement the accessors returning `list[dict]`/`dict` via `df.to_dict("records")`. `historical_requirements()` = requirements where `program_id != showcase_program_id`.

- [ ] **Step 5: Run.** `python data_generation/generate_synthetic_data.py` then `python -m pytest tests/test_source.py -v` and `python common/source.py` → PASS.
- [ ] **Step 6: Commit.** `git add -A && git commit -m "feat: synthetic csv source + source layer"`.

---

## Task 3: Deterministic test bench

**Files:**
- Create: `02_backend/engineering/test_bench.py`
- Test: `02_backend/tests/test_test_bench.py`

**Interfaces:** Consumes `source.list_test_plans`, `source.list_design_specs`. Produces `run_test_bench(program_id)`; writes `test_results`.

**Formula (deterministic, no physics):** for each `test_plan`, find the design spec on the same `req_id`; compute `measured_value` from spec value via a fixed per-category function; `margin = (measured - target)/target`. Verdict: `margin >= 0.10` → PASS; `0 <= margin < 0.10` → MARGINAL; `margin < 0` → FAIL. Tune the showcase thermal spec so its margin ≈ 0.03 (MARGINAL).

- [ ] **Step 1: Write the failing test:**

```python
from common.db import init_db
from engineering.test_bench import run_test_bench

def test_bench_is_deterministic_and_thermal_is_marginal(tmp_path, monkeypatch):
    init_db()
    r1 = run_test_bench("PACK-ATLAS-01")
    r2 = run_test_bench("PACK-ATLAS-01")
    assert [ (x["test_id"],x["measured_value"],x["verdict"]) for x in r1 ] == \
           [ (x["test_id"],x["measured_value"],x["verdict"]) for x in r2 ]
    verdicts = {x["test_id"]: x["verdict"] for x in r1}
    assert "MARGINAL" in verdicts.values()
    # the thermal test is the marginal one
    thermal = [x for x in r1 if x["test_id"].startswith("T-ATLAS-thermal")]
    assert thermal and thermal[0]["verdict"] == "MARGINAL"
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Write `engineering/test_bench.py`:**

```python
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
```

  > Note: uses `uuid5` (deterministic) for result ids — NOT `uuid4`. `test_id` naming convention `T-<PROGRAMSHORT>-<category>-01` is set in Task 2 so `startswith('T-ATLAS-thermal')` holds.

- [ ] **Step 4: Run** `python -m pytest tests/test_test_bench.py -v` and `python engineering/test_bench.py` → PASS. If thermal isn't MARGINAL, adjust the showcase thermal spec `value` in Task 2 (data), not the formula.
- [ ] **Step 5: Commit.** `git commit -am "feat: deterministic test bench"`.

---

## Task 4: Traceability + gate decision

**Files:**
- Create: `02_backend/engineering/traceability.py`
- Test: `02_backend/tests/test_traceability.py`

**Interfaces:** Consumes `source.*` + `test_results` (ops). Produces `coverage`, `build_matrix`, `missing_standards`, `decide`.

**Required standards (for missing_standards):** `REQUIRED_STANDARDS = ["UN38.3","GB 38031","IEC 62660"]` — a standard is "covered" if any test_plan.standard equals it.

**`decide` rule (pure):** `FAIL` if any test FAIL or coverage pct < 0.6; else `CONDITIONAL` if any MARGINAL or coverage gaps or missing standards; else `PASS`.

- [ ] **Step 1: Write the failing test:**

```python
from engineering.traceability import coverage, decide, missing_standards

def test_coverage_reports_gap():
    cov = coverage("PACK-ATLAS-01")
    assert cov["total"] >= 5 and cov["gaps"]           # cost req uncovered
    assert 0.0 <= cov["pct"] <= 1.0

def test_decide_is_conditional_for_showcase():
    cov = coverage("PACK-ATLAS-01")
    results = [{"verdict":"PASS"},{"verdict":"MARGINAL"}]
    assert decide(cov, results, missing_standards("PACK-ATLAS-01")) == "CONDITIONAL"

def test_decide_fail_on_failing_test():
    assert decide({"pct":1.0,"gaps":[]},[{"verdict":"FAIL"}],[]) == "FAIL"
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Write `engineering/traceability.py`:**

```python
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
```

- [ ] **Step 4: Run tests → PASS.**
- [ ] **Step 5: Commit.** `git commit -am "feat: traceability + gate decision"`.

---

## Task 5: Traditional ML — design-risk model

**Files:**
- Create: `02_backend/ml/train.py`, `02_backend/ml/risk_model.py`
- Test: `02_backend/tests/test_risk_model.py`

**Interfaces:** Consumes `source.*` + `test_results`. Produces `build_features`, `train`, `score_program`, `get_scores`, `explain`; writes `design_risk_scores`; saves `models/risk_model.pkl` + `models/risk_meta.json`.

**Label:** per requirement, label=1 if its test verdict ∈ {FAIL,MARGINAL} else 0. Train on historical programs; score the showcase. **Features (numeric):** `[target_value, spec_value, margin, bom_cost, bom_mass, supplier_quality, is_thermal, is_safety]`. Seeding (Task 2) must make `is_thermal=1` co-occur with label=1 in history so the showcase thermal requirement predicts HIGH. Band: `risk_prob>=0.66`→HIGH, `>=0.33`→MEDIUM, else LOW.

- [ ] **Step 1: Write the failing test:**

```python
from ml.train import train
from ml.risk_model import score_program, get_scores, explain
from common.db import init_db
from engineering.test_bench import run_test_bench

def test_train_and_score_thermal_high_and_deterministic():
    init_db()
    for p in ["PACK-ORION-00","PACK-VEGA-00","PACK-ATLAS-01"]:
        run_test_bench(p)
    v = train()
    assert v
    s1 = score_program("PACK-ATLAS-01")
    s2 = score_program("PACK-ATLAS-01")
    assert [(x["entity_id"],x["risk_band"]) for x in s1] == [(x["entity_id"],x["risk_band"]) for x in s2]
    thermal = [x for x in s1 if "thermal" in x["entity_id"]]
    assert thermal and thermal[0]["risk_band"] == "HIGH"
    assert len(explain()) == 5
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Write `ml/train.py`** — `build_features(programs)` joins requirements↔specs↔bom↔suppliers↔test_results into one row/requirement with the 8 features + label; `train()` fits `sklearn.ensemble.GradientBoostingClassifier(random_state=42)` on historical programs, saves model via `pickle` to `models/risk_model.pkl`, saves `{"model_version","features"}` to `models/risk_meta.json`, returns model_version (e.g. `rm-<hash of feature matrix>`). Self-check asserts train accuracy on history == 1.0 (tiny separable set).
- [ ] **Step 4: Write `ml/risk_model.py`** — `score_program` builds features for the program's requirements, `predict_proba`, writes `design_risk_scores` rows (`entity_type='requirement'`, `entity_id=req_id` — ensure req_ids contain the category e.g. `REQ-ATLAS-thermal` so the test's substring check holds), returns list; `get_scores` reads them back; `explain()` returns top-5 `feature_importances_`.
- [ ] **Step 5: Run tests → PASS.** If thermal isn't HIGH, strengthen the historical thermal→failure signal in Task 2 seeding (not the model).
- [ ] **Step 6: Commit.** `git commit -am "feat: sklearn design-risk model + inference"`.

---

## Task 6: Ontology layer

**Files:**
- Create: `02_backend/knowledge/ontology.yaml`, `02_backend/knowledge/ontology.py`
- Test: `02_backend/tests/test_ontology.py`

**Interfaces:** Produces `load_ontology`, `classes`, `relations`, `describe`, `validate_asset`.

- [ ] **Step 1: Write the failing test:**

```python
from knowledge import ontology

def test_ontology_classes_and_relations():
    cs = ontology.classes()
    assert {"DesignImage","SpecSheet","TestReport","ComponentPhoto","RequirementDoc"}.issubset(set(cs))
    rels = ontology.relations()
    assert any(r["from"]=="DesignImage" and r["to"]=="Requirement" for r in rels)
    assert ontology.validate_asset({"ontology_class":"DesignImage"})
    assert not ontology.validate_asset({"ontology_class":"Nonsense"})
    assert ontology.describe("TestReport")["description"]
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Write `ontology.yaml`:**

```yaml
classes:
  Requirement:     {description: "An engineering requirement", modality: structured}
  DesignImage:     {description: "CAD/thermal map illustrating a design", modality: image}
  SpecSheet:       {description: "Component or design spec sheet", modality: pdf}
  TestReport:      {description: "DVP&R test report / result excerpt", modality: text}
  ComponentPhoto:  {description: "Photo of a physical component/module", modality: image}
  RequirementDoc:  {description: "Source requirement document", modality: text}
relations:
  - {from: DesignImage,    rel: illustrates, to: Requirement}
  - {from: TestReport,     rel: evidences,   to: TestPlan}
  - {from: ComponentPhoto, rel: depicts,     to: Part}
  - {from: SpecSheet,      rel: specifies,   to: DesignSpec}
```

- [ ] **Step 4: Write `ontology.py`** — load YAML once (cache), `classes()` = list(yaml["classes"]), `relations()` = yaml["relations"], `describe(cls)` = yaml["classes"][cls], `validate_asset(a)` = a.get("ontology_class") in classes(). Self-check asserts ≥5 classes.
- [ ] **Step 5: Run → PASS.**
- [ ] **Step 6: Commit.** `git commit -am "feat: engineering ontology layer"`.

---

## Task 7: Multimodal KB (Lance) + seeded assets

**Files:**
- Create: `02_backend/knowledge/kb.py`, `02_backend/data_generation/generate_assets.py`
- Create: `data/kb/raw/` seed assets (generated)
- Test: `02_backend/tests/test_kb.py`

**Interfaces:** Consumes `ontology.validate_asset`. Produces `embed`, `build_kb`, `search`, `get_asset`; writes `data/kb/assets.lance`.

**Embedding:** try `sentence-transformers` MiniLM if importable/offline-cached; else deterministic hashing embedding (`_hash_embed`: 128-dim, token-hash bag, L2-normalized). Precompute at `build_kb` time and store vectors in Lance → runtime `search` only computes the query vector (same `embed`) + cosine via Lance vector index. Determinism guaranteed by hashing fallback.

**Assets (~10):** `generate_assets.py` makes tiny PNGs (numpy→PNG via `pylance`/`PIL` if available, else 1×1 gray PNG bytes) + markdown/text; each asset dict: `{asset_id, ontology_class, modality, title, caption_text, blob, program_ref, linked_entity_type, linked_entity_id}`. Include a `PACK-ORION-00` `DesignImage` + `TestReport` linked to its thermal requirement (the reuse hit).

- [ ] **Step 1: Write the failing test:**

```python
from knowledge.kb import build_kb, search, get_asset

def test_kb_builds_validates_and_thermal_query_hits():
    n = build_kb()
    assert n >= 8
    hits = search("thermal runaway containment design", k=3)
    assert hits and any("thermal" in (h.get("linked_entity_id") or "") for h in hits)
    top = hits[0]
    a = get_asset(top["asset_id"])
    assert a["blob"] and a["modality"] in {"image","pdf","text"}

def test_search_is_deterministic():
    build_kb()
    a = [h["asset_id"] for h in search("thermal", k=3)]
    b = [h["asset_id"] for h in search("thermal", k=3)]
    assert a == b
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Write `knowledge/kb.py`** — `embed(text)` (ST-or-hash), `_hash_embed`, `build_kb()` reads assets from `generate_assets.build_assets()`, validates each via `ontology.validate_asset` (assert), computes embeddings, writes a Lance dataset with a fixed-size `embedding` vector column + blob + scalars (use `lance.write_dataset` with a pyarrow table; vector column as `list<float32>[dim]`). `search(query, ontology_filter, k)` opens the dataset, runs vector search (`dataset.to_table(nearest={...})` or cosine over the column if the installed pylance lacks an index for this size — small N, brute-force cosine is fine and deterministic), returns hits sorted by score with a stable tiebreak on `asset_id`. `get_asset(id)` filters the dataset by `asset_id`.
  > ponytail: for ~10 rows, brute-force cosine in numpy is simpler and more deterministic than building an ANN index; add an index only if N grows.
- [ ] **Step 4: Write `generate_assets.py`** — `build_assets() -> list[dict]` returns the ~10 seeded assets with `blob` bytes; deterministic content.
- [ ] **Step 5: Run tests → PASS.**
- [ ] **Step 6: Commit.** `git commit -am "feat: lance multimodal kb + seeded assets"`.

---

## Task 8: State machine + agent tools

**Files:**
- Create: `02_backend/agents/state_machine.py` (copy AML, new enum)
- Create: `02_backend/common/evidence.py` (copy AML, rename)
- Create: `02_backend/agents/tools.py`
- Test: `02_backend/tests/test_tools.py`

**Interfaces:** Produces `ProgramState`/`transition`, `create_evidence`/`list_review_evidence`, and `TOOLS` registry.

- [ ] **Step 1:** Copy AML `agents/state_machine.py`; replace enum with `ProgramState` (REQUIREMENTS→DESIGN→ENGINEERING→VALIDATION→GATE_REVIEW→RELEASED) and the `_ALLOWED` chain. Copy AML `common/evidence.py`; rename `case_id`→`review_id`, `list_case_evidence`→`list_review_evidence`, table stays `evidence`.
- [ ] **Step 2: Write the failing test** `tests/test_tools.py`:

```python
from agents.tools import TOOLS

def test_tools_registry_has_all():
    for name in ["get_program","list_requirements","get_traceability","get_test_results",
                 "get_design_risk","get_model_explanation","kb_search","get_asset","ontology_describe"]:
        assert name in TOOLS and callable(TOOLS[name])

def test_get_design_risk_returns_scores():
    from common.db import init_db; from engineering.test_bench import run_test_bench
    from ml.train import train
    init_db()
    for p in ["PACK-ORION-00","PACK-VEGA-00","PACK-ATLAS-01"]: run_test_bench(p)
    train()
    out = TOOLS["get_design_risk"](None, "PACK-ATLAS-01")
    assert any(x["risk_band"]=="HIGH" for x in out)
```

- [ ] **Step 3: Run → FAIL.**
- [ ] **Step 4: Write `agents/tools.py`** — thin wrappers over `source`, `traceability`, `test_results` (ops read), `risk_model.get_scores` + `explain`, `kb.search`/`get_asset`, `ontology.describe`. Signature `fn(conn, *args)` (conn may be None) mirroring AML. `TOOLS` dict registry.
- [ ] **Step 5: Run → PASS.**
- [ ] **Step 6: Commit.** `git commit -am "feat: state machine, evidence, agent tools"`.

---

## Task 9: Agent workers + supervisor (SSE) + narrative

**Files:**
- Create: `02_backend/agents/workers.py`, `02_backend/agents/narrative.py`, `02_backend/agents/supervisor.py`
- Test: `02_backend/tests/test_gate_review.py`

**Interfaces:** Produces the 5 workers, `narrate`, `run_gate_review` (generator of event dicts). Recommendation via `traceability.decide`.

- [ ] **Step 1: Write the failing test:**

```python
from agents.supervisor import run_gate_review
from common.db import init_db
from engineering.test_bench import run_test_bench
from ml.train import train
from knowledge.kb import build_kb

def test_gate_review_deterministic_recommendation_and_evidence():
    init_db()
    for p in ["PACK-ORION-00","PACK-VEGA-00","PACK-ATLAS-01"]: run_test_bench(p)
    train(); build_kb()
    def rec(events):
        types=[e["type"] for e in events]
        r=[e["value"] for e in events if e["type"]=="recommendation"][0]
        workers=[e["worker"] for e in events if e["type"]=="worker_done"]
        return types, r, workers
    e1=list(run_gate_review("REV-1","PACK-ATLAS-01"))
    e2=list(run_gate_review("REV-2","PACK-ATLAS-01"))
    t1,r1,w1=rec(e1); t2,r2,w2=rec(e2)
    assert r1==r2=="CONDITIONAL"
    assert set(w1)=={"coverage","testverdict","compliance","designrisk","knowledgereuse"}
    assert e1[-1]["type"]=="done"
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Write `agents/workers.py`** — each worker: fetch its data via `TOOLS`, `create_evidence(review_id, tool, query, payload, "src-v1", worker)`, call `chat(...)` once for a 3-bullet finding (deterministic wording not required — findings are prose), return `{"worker","findings","evidence_ids"}`. `designrisk` uses `get_design_risk`+`get_model_explanation` and MUST include the numeric HIGH score + top feature in `findings`. `knowledgereuse` uses `kb_search("thermal ...")` + `ontology_describe` and MUST cite the retrieved asset's `ontology_class` + `asset_id`. If `chat` raises, catch and use a template finding (never fail).
- [ ] **Step 4: Write `agents/narrative.py`** — `narrate(program_id, findings, recommendation)`: build a system+user message summarizing findings, `for tok in chat(msgs, stream=True): yield tok`; wrap in try/except → on error `yield` a deterministic template (`f"Gate review for {program_id}: recommendation {recommendation}. ..."`).
- [ ] **Step 5: Write `agents/supervisor.py`** — mirror AML `run_investigation`: phase COLLECTING → `ThreadPoolExecutor` fan-out the 5 workers, yield `worker_start`/`worker_done`; compute `rec = decide(coverage(pid), test_results, missing_standards(pid))`, yield `{"type":"recommendation","value":rec}`; phase ANALYZING → stream `narrate(...)` tokens; write `gate_reviews` row (recommendation + assembled narrative); yield `done`. Use `ProgramState` transitions.
- [ ] **Step 6: Run tests → PASS.**
- [ ] **Step 7: Commit.** `git commit -am "feat: agent workers + supervisor SSE gate review"`.

---

## Task 10: FastAPI backend

**Files:**
- Create: `02_backend/api/main.py`, `02_backend/start_backend.py` (copy AML)
- Test: `02_backend/tests/test_api.py`

**Interfaces:** Consumes all backend modules. Produces the HTTP surface.

**Endpoints:**
- `GET /api/programs` → list_programs
- `GET /api/programs/{pid}` → program + coverage + matrix
- `GET /api/programs/{pid}/requirements|design|bom|tests`
- `GET /api/programs/{pid}/results` → test_results (ops)
- `GET /api/programs/{pid}/risk` → get_scores + explain
- `GET /api/programs/{pid}/matrix` → build_matrix
- `POST /api/programs/{pid}/testbench` → run_test_bench (idempotent)
- `GET /api/kb/search?q=&cls=` → kb.search
- `GET /api/asset/{asset_id}` → StreamingResponse(blob, media_type by modality)
- `GET /api/ontology` → classes+relations
- `GET /api/review/{pid}/stream` → SSE wrapping `run_gate_review` (each event → `data: {json}\n\n`)
- `POST /api/review/{review_id}/decision` → write annotations + gate_reviews.decision

- [ ] **Step 1: Write the failing test** using `fastapi.testclient.TestClient` — assert `/api/programs` returns 3, `/api/programs/PACK-ATLAS-01/risk` has a HIGH, `/api/kb/search?q=thermal` non-empty, `/api/asset/{id}` returns 200 bytes.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Write `api/main.py`** — mirror AML `api/main.py` structure: FastAPI app, sync endpoints reading via a per-request `get_connection()` where needed, SSE endpoint as a `StreamingResponse(generator, media_type="text/event-stream")` mapping each dict to `f"data: {json.dumps(ev)}\n\n"`. Copy AML `start_backend.py`.
- [ ] **Step 4: Run tests → PASS.**
- [ ] **Step 5: Commit.** `git commit -am "feat: fastapi backend"`.

---

## Task 11: Frontend — Dashboard A (Program Cockpit)

**Files:**
- Copy AML `03_frontend/` scaffold (Vite, Tailwind, `main.tsx`, `index.css`, `api.ts`, `start_frontend.py`, `package.json`, config).
- Create: `03_frontend/src/App.tsx` (route `/program`), `src/components/{StageTracker,RequirementsTable,RiskPanel,TraceabilityMatrix,GateReview,KnowledgeCards,DecisionControl}.tsx`, `src/api.ts` (typed fetchers + SSE helper).

**Data contracts the components consume** (match Task 10 JSON):
- `RiskPanel`: `GET /api/programs/{pid}/risk` → `[{entity_id, risk_prob, risk_band, top_features}]`
- `TraceabilityMatrix`: `/matrix` → `{rows:[{req_id,category,spec_id,test_id,verdict}]}`
- `GateReview`: SSE `/api/review/{pid}/stream` events `phase|worker_start|worker_done|recommendation|token|done`
- `KnowledgeCards`: `/api/kb/search?q=` → hits; image via `/api/asset/{id}`
- `DecisionControl`: `POST /api/review/{review_id}/decision`

- [ ] **Step 1:** Copy AML `03_frontend/`; `npm install`; confirm `npm run dev` serves the AML scaffold. Replace branding.
- [ ] **Step 2:** Write `src/api.ts` — `getPrograms()`, `getProgram(pid)`, `getRisk(pid)`, `getMatrix(pid)`, `searchKb(q)`, `assetUrl(id)`, `streamReview(pid, onEvent)` (uses `EventSource` or `fetch`+`ReadableStream` — copy AML's SSE helper), `postDecision(reviewId, body)`.
- [ ] **Step 3:** Build components (Tailwind, follow AML component style). `GateReview`: button → open SSE → render worker cards as `worker_done` arrives, show streamed narrative tokens, badge the `recommendation`. `RiskPanel`: ranked list, HIGH in red. `TraceabilityMatrix`: req×(design,test,verdict) grid, gaps highlighted. `KnowledgeCards`: thumbnails (`<img src={assetUrl(id)}>`) + ontology class + linked entity.
- [ ] **Step 4:** Wire `App.tsx` layout: StageTracker (top) → left: Requirements/Design + RiskPanel; center: TraceabilityMatrix + GateReview; right: KnowledgeCards; footer: DecisionControl.
- [ ] **Step 5: Manual verify.** `python start_app.py` → open `http://localhost:8100/program`: Run Gate Review streams, recommendation = CONDITIONAL, risk panel shows thermal HIGH, knowledge cards show a retrieved asset, decision submits. (Use the webapp-testing skill for a scripted check if desired.)
- [ ] **Step 6: Commit.** `git commit -am "feat: dashboard A program cockpit"`.

---

## Task 12: Workbench packaging + docs

**Files:**
- Create: `.project-metadata.yaml`, `README.md`
- Verify: `01_installer/install.py`, `start_app.py`

**AMP tasks (in `.project-metadata.yaml`, mirror AML order):** 1) Install Dependencies (`01_installer/install.py`) 2) Generate Synthetic Data (`data_generation/generate_synthetic_data.py`) 3) Init DB + Test Bench (`common/db.py::init_db` + run bench for 3 programs — small `scripts/prepare.py`) 4) Train Risk Model (`ml/train.py`) 5) Build Lance KB (`knowledge/kb.py::build_kb`) 6) Start App (`start_app.py`).

- [ ] **Step 1:** Write `scripts/prepare.py` — `init_db()`; `run_test_bench` for all 3 programs; `train()`; `build_kb()`; print a summary. (One idempotent bootstrap the AMP + local dev both call.)
- [ ] **Step 2:** Write `.project-metadata.yaml` (copy AML shape; the 6 tasks above; env `BACKEND_PORT`, `LLM_PROVIDER`).
- [ ] **Step 3:** Write `README.md` — the demo narrative, quick start (`pip install -r requirements.txt` → `cp config` → `python scripts/prepare.py` → `python start_app.py`), the ML↔agentic + multimodal story, the two-store split, extension list.
- [ ] **Step 4: End-to-end verify locally.** Fresh venv → follow README → open `/program` → run the demo flow. Then confirm the AMP task scripts each run standalone.
- [ ] **Step 5: Commit.** `git commit -am "feat: workbench AMP packaging + readme"`.

---

## Verification (whole Phase 1)

- `python -m pytest 02_backend/tests -v` → all green.
- `python 02_backend/data_generation/generate_synthetic_data.py` twice → identical CSV hashes.
- `python 02_backend/scripts/prepare.py` → DB + model + Lance built; thermal test MARGINAL, thermal risk HIGH.
- Headless gate review script → recommendation `CONDITIONAL` stable across runs; 5 worker_done + evidence rows; designrisk cites ML score; knowledgereuse cites an asset by ontology class.
- `python start_app.py` → `/program`: gate review streams, recommendation badge, risk panel (thermal HIGH), knowledge cards (retrieved asset), decision persists.
- Deploy as CAI AMP on Workbench; run the 6 tasks in order; open the app; run the demo flow end-to-end.

## Self-Review (completed)

- **Spec coverage:** every Phase-1 task in the design plan maps here — CSV source + source layer (T2), SQLite ops (T1), test-bench (T3), traceability+decide (T4), ML risk (T5), ontology (T6), Lance multimodal (T7), tools/state/evidence (T8), workers/supervisor/narrative SSE (T9), API (T10), Dashboard A (T11), Workbench packaging (T12). Iceberg-MCP, Dashboard B, live generation, Chroma→remain explicitly out (Phase 2+).
- **Type consistency:** signatures pinned in the Interfaces block are used verbatim in every task (`run_test_bench`, `decide(cov,results,missing_std)`, `score_program`/`get_scores`/`explain`, `search(query,ontology_filter,k)`/`get_asset`, worker return `{"worker","findings","evidence_ids"}`, event `{"type":"recommendation","value":...}`).
- **Determinism:** seeds fixed; `uuid5` not `uuid4`; embeddings precomputed with hashing fallback; recommendation is a pure function; LLM confined to `narrate()` with template fallback.
- **Known tuning knobs (physical-world calibration):** the showcase thermal spec value (T2) is tuned so the bench margin lands MARGINAL and history makes thermal predict HIGH — adjust the *data*, never the formula/model, if an assert misses.
