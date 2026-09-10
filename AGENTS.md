# AGENTS.md

> First thing an AI agent should read when entering this repo. Start here, then follow the links.

## What this is

**Vehicle Manufacturing Blueprint** — a Workbench-deployable, *deterministic* agentic demo of a New Product Introduction (NPI) lifecycle, concretized on an EV battery-pack program. It mirrors the architecture of `../anti_money_laundry_blueprint` (AML) and swaps the domain to automotive/manufacturing (APQP gate reviews, DVP&R test results, traceability matrix, design-risk ML).

Phase 1 (walking skeleton) is **complete**: CSV source + SQLite ops + Lance multimodal KB, a deterministic test bench + traceability, a traditional-ML design-risk model, an ontology layer, a 5-agent SSE "Gate Review", a FastAPI backend, and a React "Program Cockpit" (Dashboard A).

## The one rule that governs everything

**Code decides, LLM narrates.** Every number and every decision (test verdicts, coverage %, the PASS/CONDITIONAL/FAIL gate recommendation, ML risk bands) is a pure function over seeded data — identical every run. The LLM only writes prose (agent findings, the gate narrative) and **always has a deterministic template fallback**, so the demo runs fully offline with no LLM configured. Never let an LLM output influence a decision, a verdict, a score, or control flow.

Corollaries you must respect:
- **Determinism is sacred.** Fixed `SEED=42`. `uuid5` not `uuid4` for computed IDs. No `datetime.now()`/`random()` in computed artifacts (fine in frontend JS). Re-running any generator/computation is byte-identical.
- **Two-store rule.** Source/reference data (`common/source.py`, CSV under `data/raw/`) is **read-only** — never written by the app. Runtime writes go to **SQLite ops** (`data/npi.db` via `common/db.py`) or are **Lance build-time only** (`data/kb/assets.lance`).
- **Every Python module ends with an `if __name__ == "__main__":` assert-based self-check.** Self-checks that touch the DB must use a throwaway temp DB (override `common.db.get_db_path`), never the real `data/npi.db`.
- **Every backend module imports via** `sys.path.insert(0, .../02_backend)` (see any module for the pattern).

## The demo spine (don't break this)

Showcase program `PACK-ATLAS-01`'s **thermal requirement scores ML HIGH** *and* its **thermal DVP&R test is MARGINAL** — two structurally independent computations that corroborate by seed construction. The gate review yields **CONDITIONAL**. If you change seed data and an assert about this breaks, fix the *data* (in `generate_synthetic_data.py`), never the formula/model. See [docs/demo_storyline.md](docs/demo_storyline.md).

## Run it

```bash
pip install -r requirements.txt
cp config/config.yaml.example config/config.yaml   # may already exist
python 02_backend/scripts/prepare.py               # idempotent bootstrap: DB + test-bench + train + KB
python start_app.py                                # local dev launcher → http://localhost:8100
```
Tests: `cd 02_backend && python -m pytest tests/ -q` (36 tests) · frontend type-check: `cd 03_frontend && npm run build`.

## Where things live

| Path | What |
|------|------|
| `02_backend/common/` | `config.py`, `db.py` (SQLite ops), `source.py` (CSV read-only), `evidence.py`, `caii.py` |
| `02_backend/data_generation/` | `schema.py` (ops tables), `generate_synthetic_data.py` (seeded CSVs), `generate_assets.py` (KB blobs) |
| `02_backend/engineering/` | `test_bench.py` (deterministic verdicts), `traceability.py` (coverage/matrix/`decide`) |
| `02_backend/ml/` | `train.py`, `risk_model.py` (sklearn design-risk) |
| `02_backend/knowledge/` | `ontology.py`+`ontology.yaml`, `kb.py` (Lance multimodal search) |
| `02_backend/agents/` | `state_machine.py`, `tools.py`, `workers.py` (5 workers), `supervisor.py` (SSE), `narrative.py`, `llm_client.py` |
| `02_backend/api/main.py` | FastAPI HTTP surface (16 routes) |
| `02_backend/scripts/prepare.py` | one-shot idempotent bootstrap (also a smoke test) |
| `03_frontend/` | React 19 + Vite + Tailwind 4 — Dashboard A "Program Cockpit" |

## Read next

- [docs/project-overview.md](docs/project-overview.md) — what & why, at a glance
- [docs/architecture.md](docs/architecture.md) — the three stores, data flow, the gate-review pipeline
- [docs/development.md](docs/development.md) — commands, conventions, regression checklist
- [docs/component-api.md](docs/component-api.md) — backend module signatures + HTTP + React component contracts
- [docs/user-guide.md](docs/user-guide.md) — the demo from a user's seat
- [docs/DESIGN.md](docs/DESIGN.md) — visual system (tokens, brand chrome)
- [docs/TODO.md](docs/TODO.md) — current status + Phase 2 backlog
- [docs/demo_storyline.md](docs/demo_storyline.md) — the scripted demo narrative

The authoritative build plan is `docs/superpowers/plans/2026-09-07-phase1-walking-skeleton.md`; the per-task execution ledger is `.superpowers/sdd/progress.md` (gitignored scratch).
