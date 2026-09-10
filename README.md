# Vehicle NPI Blueprint

An agentic gate-review platform for vehicle New Product Introduction (NPI)
programs. It pairs a deterministic engineering test bench and traceability
matrix with a CPU-only design-risk model, a multimodal knowledge base of
prior-program assets, and a 5-agent swarm that audits a program and produces
a code-computed gate recommendation for a human to approve.

## Demo narrative

`PACK-ATLAS-01`, an EV battery-pack NPI program, is at its release gate. Its
thermal-runaway containment requirement has a razor-thin margin: the
deterministic test bench measures the part against its design spec and
verdicts the thermal test **MARGINAL** — not a failure, but not comfortable
either. Independently, a traditional ML model (a `GradientBoostingClassifier`
trained on requirement features from two completed historical programs)
scores that same requirement's design risk as **HIGH**. The ML score didn't
invent this — it's corroborated by the measured test result. Two different
methods, one conclusion, that's the story we want the reviewer to see.

Clicking **Run Gate Review** kicks off a 5-agent swarm (coverage,
test-verdict, compliance, design-risk, knowledge-reuse) that audits the
program in parallel, streaming its findings live over SSE. The DesignRisk
agent explains *why* the model flagged the requirement (top feature
importances, corroborated by the measured verdict). The KnowledgeReuse agent
searches the Lance-backed knowledge base and retrieves a prior program's
design image and test report — filtered through the engineering ontology so
only valid asset classes are surfaced — to show how a similar issue was
handled before. A supervisor then applies a pure, deterministic decision
function (`decide(coverage, results, missing_standards)`) over the audited
evidence to produce **PASS / CONDITIONAL / FAIL** — the LLM narrates *why*,
it never decides. A human engineer reviews the evidence and makes the final
gate call, which is persisted.

## Quick start

```bash
pip install -r requirements.txt
cp config/config.yaml.example config/config.yaml   # already present if you ran 01_installer/install.py
python 02_backend/data_generation/generate_synthetic_data.py
python 02_backend/scripts/prepare.py                # init DB, run test bench, train model, build KB
python start_app.py
```

Open `http://localhost:8100` (the port `start_app.py` prints). The single
Dashboard A cockpit page shows the program's requirements, risk panel,
traceability matrix, the gate-review runner, and the retrieved knowledge
cards for `PACK-ATLAS-01`.

`start_app.py` is the local-dev launcher: it delegates to
`03_frontend/start_frontend.py`, which serves the production React build
(if `03_frontend/dist/` exists, else the Vite dev server) and starts one
co-located FastAPI backend as a child process, with `/api/*` reverse-proxied
to it — including the long-lived SSE gate-review stream. This is the same
single-process pattern the app uses when deployed as a CAI Applied ML
Prototype (AMP) on CAI Workbench: the AMP's `start_application` task points
directly at `03_frontend/start_frontend.py` for the same reason (a separate
root-level backend launcher would double-bind `BACKEND_PORT`).

No live LLM is required to run the demo: `agents/narrative.py`'s `narrate()`
falls back to a deterministic template string whenever no LLM provider is
reachable, so the gate review runs and streams fully offline. Configure
`config/config.yaml` (`caii` / `vllm` / `ollama`) if you want live narration.

## Cloudera AI AMP and GitHub deployment

This repository is an AMP. Import it through the Cloudera AI AMP catalog, then
run its tasks in this order: **Install Dependencies → Generate Synthetic Data
→ Prepare Data, Model & KB → Verify Prepared Demo → Vehicle NPI Platform**.
The final task starts the private, SSO-protected application; it does not need
an externally assigned port because Workbench supplies `CDSW_APP_PORT`.

GitHub Actions validates the AMP manifest, backend/MCP tests, and frontend on
pull requests and `main`. The `Deploy Vehicle NPI AMP to Cloudera AI` workflow
then uses the project’s API-v2 automation to create or reuse the Workbench
project, run its preparation Job, and create/restart the private application.
Set these GitHub Actions secrets before enabling a deployment:

- `CML_HOST` — HTTPS Workbench origin.
- `CML_API_KEY` — API v2 key with project, Job, and Application permissions.
- `RUNTIME_IDENTIFIER` — Python 3.11 Standard runtime identifier.
- `CML_PROJECT_ID` — optional existing project ID.
- `CML_GIT_URL` — optional cloneable HTTPS source URL; it is required when
  the repository’s default GitHub URL is not cloneable by the Workbench.

The workflow never forwards the deployment API key into a Job, Application, or
MCP client. It publishes only the non-secret deployment result as an Actions
artifact. See [cai_integration/README.md](cai_integration/README.md) for the
same flow outside GitHub Actions.

## Architecture

**Code decides, LLM narrates.** Every number a reviewer sees — test
verdicts, coverage percentage, risk scores, the PASS/CONDITIONAL/FAIL
recommendation — comes from a pure, deterministic function. The LLM (when
available) is confined to writing human-readable prose *about* those
already-computed facts; it is never on the path that produces a number or a
decision. This keeps the demo reproducible and auditable.

**Two-store split** (three, counting the knowledge base):
- **CSV source** (`data/raw/`) — read-only system of record for NPI programs,
  requirements, design specs, BOM, suppliers, and test plans. Written once by
  `data_generation/generate_synthetic_data.py`; never mutated at runtime.
- **SQLite ops store** (`data/npi.db`) — runtime state: test results, design-
  risk scores, gate reviews, agent evidence, and human decisions. Rebuilt
  idempotently by `common/db.py::init_db` plus the pipeline scripts.
- **Lance multimodal KB** (`data/kb/assets.lance`) — a separate store of
  ontology-validated prior-program assets (design images, test-report PDFs,
  captions) with precomputed embeddings, used only for knowledge-reuse
  retrieval. Never touched by the ops or source layers.

**ML ↔ ground-truth corroboration.** The design-risk model is trained on
historical programs' requirement features (target/spec values, margin, BOM
cost/mass, supplier quality, category flags) labeled by the deterministic
test bench's own verdicts (`FAIL`/`MARGINAL` → positive label). Its score for
the showcase program's thermal requirement is then checked against that same
program's actual measured test verdict — the demo works because both signals
agree, not because either one is hand-tuned to say "HIGH" in isolation.

**Agentic gate review.** A supervisor dispatches five workers — coverage,
test-verdict, compliance, design-risk, knowledge-reuse — each of which reads
from the ops store (or the KB, for knowledge-reuse) and writes structured
evidence rows. The supervisor then calls the same pure `decide()` function
engineers can call directly, and streams `worker_done` / `evidence` /
`recommendation` events over SSE so the frontend can render the review live.

## What's built vs. what's next

Built in this MVP: CSV source data + source layer, SQLite ops schema,
deterministic test bench, traceability + gate decision, the sklearn
design-risk model, the engineering ontology, the Lance multimodal knowledge
base, the agent tools/state machine/evidence trail, the 5-worker supervisor
with SSE streaming and template-fallback narration, the FastAPI backend, and
the Dashboard A React frontend.

Explicitly out of scope for Phase 1, left as seams for Phase 2+:
- **Iceberg-via-MCP source backend** — `common/source.py` already has a
  `source.backend: auto | iceberg | csv` config seam; only the CSV backend is
  implemented today.
- **Dashboard B** (engineering-ops / data-scientist view) — Dashboard A
  (program cockpit) is the only frontend surface in this MVP.
- **Richer multimodal embeddings** — the KB embeds captions with a
  sentence-transformers model when available, falling back to a
  deterministic token-hash embedding otherwise; true CLIP-style image
  embeddings for the seeded design images are not implemented.
- **Live lifecycle artifact generation** — seeded assets (design images,
  test reports) are pre-generated fixtures, not produced by a live
  generation pipeline.

## Repo layout

```
01_installer/          Install script (Python deps, Node.js, frontend build)
02_backend/             FastAPI backend: common/, engineering/, ml/, knowledge/,
                        agents/, api/, data_generation/, scripts/, tests/
03_frontend/            React + Vite dashboard, plus the co-located app launcher
config/                 config.yaml (LLM provider, data paths, demo program)
data/                   raw/ (CSV source), npi.db (ops store), kb/ (Lance dataset)
models/                 risk_model.pkl + risk_meta.json
start_app.py            Local-dev launcher (delegates to 03_frontend/start_frontend.py)
.project-metadata.yaml  CAI Workbench AMP definition
```
