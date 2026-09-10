# Architecture & Data Flow

## The three stores (two-store rule, three physical stores)

| Store | Where | Access | Written by |
|-------|-------|--------|-----------|
| **Source / reference** | `data/raw/*.csv` via `common/source.py` | **read-only** | `data_generation/generate_synthetic_data.py` (build time) |
| **Ops / runtime** | `data/npi.db` (SQLite, WAL) via `common/db.py` | read/write at runtime | test bench, risk model, gate review |
| **Multimodal KB** | `data/kb/assets.lance` (Lance) via `knowledge/kb.py` | read at runtime, write at build | `knowledge/kb.py::build_kb()` |

**Rule:** the app never writes source data. All runtime mutation lands in SQLite ops; Lance is written only at build time. `common/source.py` exposes a `backend: auto|iceberg|csv` seam — Phase 1 implements `csv`; `iceberg` raises "not configured" (Phase 2).

### Source tables (CSV)
`programs`, `requirements`, `design_specs`, `bom_items`, `suppliers`, `test_plans`.

### Ops tables (SQLite — `data_generation/schema.py`)
`test_results` (test-bench verdicts) · `design_risk_scores` (ML output) · `gate_reviews` (recommendation + narrative + human decision) · `evidence` (hashed agent tool payloads) · `annotations` (human gate decisions) · `llm_models` (in-app model registry).

### Lance columns
`asset_id, ontology_class, modality (image|pdf|text), title, caption_text, blob (bytes), embedding (float32 vector), program_ref, linked_entity_type, linked_entity_id`. Embeddings are **precomputed at build** (deterministic hashing fallback when `sentence-transformers` isn't offline-cached), so runtime search is model-free.

## Deterministic compute (the "code decides" core)

- **`engineering/test_bench.py`** — `run_test_bench(pid)` computes each DVP&R `measured_value` from the design spec value (`FACTOR` = 1.0 per category in Phase 1), `margin = (measured - target)/target`, and a verdict: `margin ≥ 0.10 → PASS`, `0 ≤ margin < 0.10 → MARGINAL`, `margin < 0 → FAIL`. Result IDs use `uuid5` (deterministic). Writes `test_results`.
- **`engineering/traceability.py`** — `coverage(pid)` (traced vs. gaps), `build_matrix(pid)` (req→spec→test→verdict grid), `missing_standards(pid)` (against `REQUIRED_STANDARDS = ["UN38.3","GB 38031","IEC 62660"]`), and the pure decision function:
  ```
  decide(cov, results, missing_std):
    FAIL         if any test FAIL  or coverage pct < 0.6
    CONDITIONAL  elif any MARGINAL or coverage gaps or missing standards
    PASS         otherwise
  ```
- **`ml/train.py` + `ml/risk_model.py`** — `GradientBoostingClassifier(random_state=42)` trained on the two historical programs; features `[target_value, spec_value, margin, bom_cost, bom_mass, supplier_quality, is_thermal, is_safety]`, label = 1 if a requirement's test verdict ∈ {FAIL, MARGINAL}. Scores the showcase → `design_risk_scores`. Bands: `≥0.66 HIGH`, `≥0.33 MEDIUM`, else LOW.

The recommendation, verdicts, coverage, and risk bands are **pure functions over seeded data** — no LLM anywhere in this path.

## Knowledge layer

- **`knowledge/ontology.py` + `ontology.yaml`** — 6 classes (`Requirement, DesignImage, SpecSheet, TestReport, ComponentPhoto, RequirementDoc`) and relations (`DesignImage –illustrates→ Requirement`, `TestReport –evidences→ TestPlan`, …). `validate_asset`, `classes`, `relations`, `describe`. The semantic seam that tells agents *what a blob is* and *how it links*.
- **`knowledge/kb.py`** — `build_kb()`, `search(query, ontology_filter, k)` (brute-force cosine over ~10 rows, deterministic), `get_asset(id)`. `ontology_filter` is validated against `ontology.classes()` and `asset_id` against a safe pattern before entering any Lance filter string (injection/crash hardening).

## Agentic gate review pipeline

```
run_gate_review(review_id, program_id)  →  generator of SSE event dicts
  phase COLLECTING
    ThreadPoolExecutor fan-out of 5 read-only workers (agents/workers.py):
      coverage · testverdict · compliance · designrisk · knowledgereuse
      each: fetch via agents/tools.TOOLS → create_evidence(...) → chat() once (template fallback) → {worker, findings, evidence_ids}
    yield worker_start / worker_done per worker
  recommendation = traceability.decide(coverage, test_results, missing_standards)   # ← code decides
  yield {"type":"recommendation","value": PASS|CONDITIONAL|FAIL}
  phase ANALYZING
    stream narrate(program_id, findings, recommendation) tokens   # ← LLM narrates (or one template string)
  persist gate_reviews row; state GATE_REVIEW → RELEASED (state_machine.transition)
  yield done
```
`agents/tools.py` `TOOLS` registry wraps the read-only accessors (`get_program`, `list_requirements`, `get_traceability`, `get_test_results`, `get_design_risk`, `get_model_explanation`, `kb_search`, `get_asset`, `ontology_describe`). Every worker's data fetch is logged as hashed `evidence` (the audit trail). The human decision (`POST /api/review/{review_id}/decision`) writes `annotations` + finalizes `gate_reviews.decision` + `state='RELEASED'`.

## HTTP surface (`api/main.py`)

FastAPI, permissive CORS, per-request SQLite connection via a `get_db` dependency. Sync JSON endpoints + one SSE `StreamingResponse` (`/api/review/{pid}/stream`, each event → `data: {json}\n\n`). Source-derived responses pass through `_clean()` (pandas NaN → JSON null). Full route list in [component-api.md](component-api.md).

## Frontend

React 19 + Vite + Tailwind 4 single-page cockpit. `src/api.ts` holds typed fetchers + an SSE reader (`streamSSE`) buffering across chunk boundaries. Vite dev-proxies `/api` → `localhost:$BACKEND_PORT`. On CML, `03_frontend/start_frontend.py` co-locates the backend in one process tree.

## Launchers

- `python 02_backend/scripts/prepare.py` — bootstrap (init_db + test_bench ×3 + train + build_kb; asserts thermal MARGINAL + risk HIGH).
- `python start_app.py` — **local dev**: delegates to `03_frontend/start_frontend.py` (which co-locates the backend). Ports: `BACKEND_PORT=7078`, frontend `CDSW_APP_PORT` (fallback `8100`).
- CAI AMP (`.project-metadata.yaml`) start task points at `03_frontend/start_frontend.py`.
