# Development Guide

Development approach, commands, conventions, and the regression checklist.

## Setup

```bash
pip install -r requirements.txt
cp config/config.yaml.example config/config.yaml    # if not already present
python 02_backend/scripts/prepare.py                # build DB + model + KB
```
`prepare.py` is the idempotent bootstrap (init_db + `run_test_bench` for all 3 programs + `train()` + `build_kb()`), and it asserts the demo invariants (thermal test MARGINAL, thermal risk HIGH) — so running it clean is also a smoke test.

## Run

```bash
python start_app.py                    # local dev → http://localhost:8100 (proxies /api → :7078)
# or backend only:
python 02_backend/start_backend.py     # FastAPI on $BACKEND_PORT (default 7078)
# or frontend dev server (co-locates backend):
cd 03_frontend && npm install && npm run dev
```

## Test / verify

```bash
cd 02_backend && python -m pytest tests/ -q          # 36 tests, must be green
cd 03_frontend && npm run build                      # tsc -b && vite build — zero TS errors is the frontend gate
cd 03_frontend && npm run lint                        # oxlint
```
Any module can be run directly to exercise its `__main__` self-check:
```bash
cd 02_backend
python common/db.py            # → db OK
python data_generation/generate_synthetic_data.py   # → prints a stable content hash
python engineering/test_bench.py       # → verdicts incl. MARGINAL
python engineering/traceability.py     # → coverage + CONDITIONAL
python ml/train.py && python ml/risk_model.py        # → thermal risk HIGH
python knowledge/kb.py                 # → thermal query hits
python agents/supervisor.py            # → full gate-review event stream ending in done
python api/main.py                     # → TestClient smoke of key endpoints
```

## Conventions (non-negotiable)

- **Python 3.11.** Every backend module starts with the `sys.path.insert(0, .../02_backend)` shim and ends with an `if __name__ == "__main__":` assert-based self-check.
- **Self-checks never touch the real DB.** If a self-check needs a DB, override `common.db.get_db_path` to a `tempfile.mkdtemp()` path (see `common/db.py` / `common/evidence.py` for the pattern).
- **Determinism:** `SEED=42`; `uuid5` not `uuid4`; no `datetime.now()`/`random()` in computed/committed artifacts. Frontend JS may use `Date.now()` (e.g. generating a `review_id`).
- **Code decides, LLM narrates:** never route a decision/verdict/score through an LLM. LLM calls (`agents/workers.py`, `agents/narrative.py`) are prose-only and wrapped in try/except with a deterministic template fallback.
- **Two-store rule:** never write to `data/raw/` from the app. Runtime writes → SQLite ops; Lance → build time only.
- **Tuning knobs:** if a demo-spine assert breaks (thermal MARGINAL / risk HIGH), fix the *data* in `generate_synthetic_data.py`, never the formula (`test_bench.py`) or the model (`ml/`). Note: the two historical programs' thermal must both FAIL for `is_thermal` to carry ML signal, and VEGA's thermal margin must differ from ORION's (−0.08 vs −0.10) or the GBM makes a degenerate tie-split.

## Commit style

`feat:` / `fix:` / `chore:` / `test:` prefixes; one task's deliverable per commit. Stage only intended files — the working tree carries gitignored scratch (`.omc/state/*`, regenerated `models/*`, `data/*`).

## Regression checklist (run before declaring any change done)

1. `python 02_backend/scripts/prepare.py` runs clean; its invariant asserts pass.
2. `python -m pytest 02_backend/tests -q` → all green (36).
3. `python 02_backend/data_generation/generate_synthetic_data.py` twice → identical hash (determinism).
4. `python 02_backend/agents/supervisor.py` twice → recommendation `CONDITIONAL` both times; 5 `worker_done` events; ends in `done`.
5. `cd 03_frontend && npm run build` → zero TS errors.
6. Boot check: `BACKEND_PORT=7099 CDSW_APP_PORT=8199 python start_app.py`, confirm exactly one backend listener + `/api/programs` reachable through the proxy, then kill it (no orphaned listeners).
7. If you touched an HTTP input path, re-check `GET /api/kb/search?cls='` → 200 (not 500) and `GET /api/asset/<bad'id>` → 404 (not 500).

## Known Phase-1 debt (non-blocking)

Unused `SOURCE_TABLES` constant; unused `react-router-dom`/`recharts` frontend deps; `aml-*` CSS token names retained from the AML scaffold; `sentence-transformers`/`Pillow` used-but-optional (guarded, not in `requirements.txt`); README doesn't state `install.py` is a prerequisite; no true fresh-venv install has been run. See [TODO.md](TODO.md).
