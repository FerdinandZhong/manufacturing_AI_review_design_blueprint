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


## Optional NiFi reader configuration

Set these variables in the backend environment before starting the app:

```bash
export NIFI_API_URL=https://your-nifi-host/nifi-api
export NIFI_PROCESS_GROUP_ID=root  # Prefer a specific process-group UUID.
# NIFI_TOKEN: bearer token, if required; set through your environment secret manager.
# NIFI_CA_BUNDLE: optional path to a trusted PEM CA bundle.
python start_app.py
```

TLS verification remains enabled. Tokens require HTTPS. Browser requests cannot supply a target URL or credentials.
The backend permits three fixed GET routes and limits each response to 4 MB.
Inventory output includes at most 100 processors, 100 connections, and 100 retained bulletins.
The reader does not import code or credentials from the reference UOB project.

Run `python -m pytest 02_backend/tests/test_nifi.py -q` for mocked live-source and sample checks.
Live deployment still requires connection validation against the intended NiFi instance.

## Unified data v2

Implemented shared revision scope, independent observations, exact report links, issue history, and shared cockpit/canvas/review metrics. See [unified-data-v2.md](unified-data-v2.md) for source contracts, endpoints, validation, and remaining production limitations.

## Demo/Pilot foundation

Data mode, read-only canonical pilot imports, source readiness, native Workbench RO/RW enforcement, same-origin mutation checks, and authenticated actor audit are implemented. See [foundation runtime and security](foundation-runtime-security.md). Pilot review execution, source freshness acceptance, real connectors, and remote Workbench acceptance remain pending.

Local development uses Demo mode on loopback. Workbench requires production proxy serving, a private Application, `NPI_AUTH_MODE=workbench`, `NPI_PUBLIC_ORIGIN`, and verified `NPI_TRUSTED_PROXY_CIDRS`. `NPI_APP_MODE` selects frontend serving and does not select the data mode.


## Knowledge v3

See [knowledge-v3.md](knowledge-v3.md) for the pinned embedding contract, build-time extraction, scoped retrieval, conservative narration, and explicit OCR command. Normal preparation and runtime never initiate paid OCR.


## Workbench NumPy / PyArrow import repair

Step 3 previously allowed NumPy 1.26.4 to remain installed while pip selected a newer PyArrow wheel requiring NumPy 2. The numerical stack is now pinned together in requirements.txt. The installer upgrades these packages and checks binary imports plus a NumPy → pandas → Arrow → Lance round trip in a new Python process. CI starts with NumPy 1.26.4 to exercise this upgrade path.

For an existing failed Workbench project, update to the latest source and run this in a session or notebook:

```python
import subprocess, sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "-r", "requirements.txt"])
```

Stop that Workbench session and start a new session before rerunning Step 3 (`02_backend/scripts/prepare.py`). Notebook cells can retain the old NumPy binary after pip installs a replacement. Repeating the import in the same kernel does not reload the binary stack. Rerun preparation to rebuild the model and knowledge artifacts with the pinned versions.

Reference: [Apache Arrow installation requirements](https://arrow.apache.org/docs/python/install.html).
