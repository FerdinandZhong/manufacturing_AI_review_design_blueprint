# Component & API Reference

Pinned contracts across the three layers. These signatures are stable — later code consumes earlier code by these exact names/types.

## Backend module interfaces

### `common/source.py` (CSV source, read-only; `backend: auto|iceberg|csv`)
```python
backend() -> str                                  # "csv" in Phase 1; "iceberg" raises "not configured"
list_programs() -> list[dict]
get_program(program_id: str) -> dict | None
list_requirements(program_id: str) -> list[dict]
list_design_specs(program_id: str) -> list[dict]
list_bom(program_id: str) -> list[dict]
list_test_plans(program_id: str) -> list[dict]
historical_requirements() -> list[dict]           # requirements of non-showcase programs
```

### `common/db.py` (SQLite ops)
```python
get_connection() -> sqlite3.Connection            # WAL, row_factory=Row, check_same_thread=False
init_db() -> None
```

### `common/evidence.py` (gate-review audit trail)
```python
create_evidence(review_id, tool, query, payload, data_version, agent_worker="") -> str
list_review_evidence(review_id: str) -> list[dict]
```

### `engineering/test_bench.py`
```python
run_test_bench(program_id: str) -> list[dict]     # computes + writes test_results; returns rows
```

### `engineering/traceability.py`
```python
coverage(program_id: str) -> dict                 # {"total","traced","gaps":[req_id],"pct"}
build_matrix(program_id: str) -> dict             # {"program_id","rows":[{req_id,category,spec_id,test_id,verdict}]}
missing_standards(program_id: str) -> list[str]   # unmet of REQUIRED_STANDARDS
decide(cov: dict, results: list[dict], missing_std: list[str]) -> str   # "PASS"|"CONDITIONAL"|"FAIL"  (pure)
```

### `ml/train.py` · `ml/risk_model.py`
```python
build_features(programs: list[str]) -> pd.DataFrame        # one row/requirement, 8 numeric features + label
train() -> str                                             # fits GBM(random_state=42), saves models/, returns model_version
score_program(program_id: str) -> list[dict]               # writes design_risk_scores; [{entity_id,risk_prob,risk_band,top_features,...}]
get_scores(program_id: str) -> list[dict]
explain() -> list[dict]                                    # top-5 [{"feature","importance"}]
```

### `knowledge/ontology.py`
```python
load_ontology() -> dict ; classes() -> list[str] ; relations() -> list[dict]
describe(cls: str) -> dict ; validate_asset(asset: dict) -> bool
```

### `knowledge/kb.py`
```python
embed(text: str) -> list[float]                   # precomputed model or deterministic hashing fallback
build_kb() -> int                                 # (re)builds assets.lance; returns row count
search(query: str, ontology_filter: str|None=None, k: int=3) -> list[dict]   # cls validated vs classes()
get_asset(asset_id: str) -> dict                  # {..., "blob": bytes, "modality"}; bad id → KeyError
```

### `agents/state_machine.py`
```python
class ProgramState(str, Enum): REQUIREMENTS, DESIGN, ENGINEERING, VALIDATION, GATE_REVIEW, RELEASED
transition(current, next) -> ProgramState         # linear chain; illegal transition asserts
```

### `agents/tools.py`
`TOOLS: dict[str, Callable]` — keys: `get_program, list_requirements, get_traceability, get_test_results, get_design_risk, get_model_explanation, kb_search, get_asset, ontology_describe`. Each `fn(conn, *args)` (conn may be None), all read-only.

### `agents/workers.py` (each returns `{"worker","findings","evidence_ids"}`)
`run_coverage_worker` · `run_testverdict_worker` · `run_compliance_worker` · `run_designrisk_worker` · `run_knowledgereuse_worker` — `(review_id, program_id) -> dict`.

### `agents/supervisor.py` · `agents/narrative.py`
```python
run_gate_review(review_id: str, program_id: str) -> Generator[dict, None, None]
narrate(program_id: str, findings: list[dict], recommendation: str) -> Iterator[str]
```
SSE event shapes: `{"type":"phase","phase":str}` · `{"type":"worker_start","worker":str}` · `{"type":"worker_done","worker":str,"findings":str,"evidence_ids":[str]}` · `{"type":"recommendation","value":str}` · `{"type":"token","text":str}` · `{"type":"done"}`.

## HTTP API (`api/main.py`, base `/api`)

| Method | Route | Returns |
|--------|-------|---------|
| GET | `/api/health` | `{"status":"ok"}` |
| GET | `/api/programs` | `Program[]` |
| GET | `/api/programs/{pid}` | `{program, coverage, matrix}` |
| GET | `/api/programs/{pid}/requirements\|design\|bom\|tests` | respective source rows |
| GET | `/api/programs/{pid}/results` | `test_results[]` (ops) |
| GET | `/api/programs/{pid}/risk` | `{scores[], explanation[]}` |
| GET | `/api/programs/{pid}/matrix` | `{program_id, rows[]}` |
| POST | `/api/programs/{pid}/testbench` | `run_test_bench` rows (idempotent) |
| GET | `/api/kb/search?q=&cls=&k=` | `KbHit[]` (blob stripped; `cls` validated) |
| GET | `/api/asset/{asset_id}` | raw bytes (media type by modality); bad id → 404 |
| GET | `/api/ontology` | `{classes[], relations[]}` |
| GET | `/api/review/{pid}/stream?review_id=` | SSE gate-review event stream |
| POST | `/api/review/{review_id}/decision` | body `{decision, rationale?, adjudicator?}` → updated `gate_reviews` row |

`decision` ∈ `APPROVED | APPROVED_WITH_CONDITIONS | REJECTED`. Unknown `pid`/`asset_id`/`review_id` → 404.

## React components (`03_frontend/src/`)

`src/api.ts` — typed fetchers (`getPrograms/getProgram/getRisk/getMatrix/getRequirements/getDesign/getBom/getTests/getResults/searchKb/getOntology/postDecision`), `assetUrl(id)`, `streamReview(pid, reviewId, onEvent)`, and the `streamSSE` reader.

| Component | Consumes | Role |
|-----------|----------|------|
| `StageTracker` | program stage | lifecycle stepper, GATE_REVIEW highlighted |
| `RequirementsTable` | `/requirements`,`/design`,`/bom` | tabbed requirement/design/BOM viewer |
| `RiskPanel` | `/risk` | ranked ML scores (HIGH in red) + top-5 feature bars |
| `TraceabilityMatrix` | `/matrix` | req×(spec,test,verdict) grid; gaps + verdicts color-coded |
| `GateReview` | SSE stream | Run button → worker cards + streamed narrative + recommendation badge |
| `KnowledgeCards` | `/kb/search`, `/asset/{id}` | multimodal cards: thumbnail + ontology class + linked entity |
| `DecisionControl` | `POST /decision` | 3-way human gate decision (gated until a review completes) |
| `Badge` / `PipelineStream` / `WorkflowGraph` | — | shared primitives reused from the scaffold |

App is a single-page cockpit (no router — Dashboard A is the only surface in Phase 1).


### Model registry additions

- `GET /api/config/llm/models`: list registered models, with masked API keys.
- `POST /api/config/llm/models`: register and activate `{alias, provider, model_identifier, api_base?, api_key?}`.
- `PUT /api/config/llm/models/{id}`: edit settings; omitted base preserves it and blank key preserves the existing credential.
- `POST /api/config/llm/models/{id}/activate`: select the active narration model.
- `POST /api/config/llm/models/{id}/test`: probe without changing the active selection; return `{ok, message}`.

KB search results additionally expose `provenance`, `source_url`, and `license_url`. Asset responses serve SVG, JPEG, and text with matching MIME types. The original model-resolution precedence remains active registry → runtime override → configuration.
