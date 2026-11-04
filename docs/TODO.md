# TODO

## Current status

**Phase 1 complete.** All 13 implementation tasks (Tasks 0–12) plus a final whole-branch review are merged on `main` (21 commits). The 36-test suite is green. The showcase program `PACK-ATLAS-01` is fully seeded and the marquee Gate Review runs deterministically end-to-end.

Run today:
```bash
python 02_backend/scripts/prepare.py   # idempotent bootstrap
python start_app.py                    # → http://localhost:8100
```

## Workspace refresh — 22 October 2026

- Complete: UOB-style pale workspace shell with Cloudera page branding and browser tab icon.
- Complete: responsive sidebar navigation, workspace search, cockpit panels, and Models page integration.
- Complete: read-only NiFi tab with separate sample/live modes, processor filters, connection exploration, and bulletin metadata.
- Verified: 68 backend tests, frontend build/lint, bootstrap invariants, repeated source hashes, and repeated CONDITIONAL gate reviews.
- Browser checks: 1440, 980, and 390 pixels; navigation, logo loading, filters, connection selection, live errors, sample recovery, and page overflow.
- Remaining deployment check: configure and verify the intended live NiFi instance. No live NiFi service was contacted during these checks.
- Scope: direct child inventory only; no nested traversal, natural-language pipeline assistant, historical logs, or flow mutations.

## Phase 2 backlog

| Item | What it unlocks |
|------|----------------|
| **Iceberg via MCP** | `source.py` `iceberg` backend: `common/iceberg_mcp.py` thin client; `generate_synthetic_data.py` dual-writes CSV+Iceberg from one pass | True lakehouse source story; agents pull reference data through MCP |
| **Dashboard B — Engineering Ops** | Traceability heatmap; change-request impact analysis ("which requirements/designs/tests does this CR touch?"); field-feedback → knowledge precipitation view | Covers doc §4.2 全流程追溯 + 版本关联 + 知识沉淀 |
| **CLIP / vision embeddings** | Replace hashing-vector fallback in `kb.py::embed()` with a real vision-language model; index images by content not just caption text | Genuine multimodal semantic search |
| **Live lifecycle generation** | `agents/lifecycle.py` per-stage context handoff — LLM drafts specs/BOM from upstream artifacts into ops working copies | Shows 上下文传递 live rather than from pre-seeded data |
| **DesignReview 5th agent** | Full design-spec vs requirement-target agent in the Gate Review swarm | Covers design-spec vs requirement gap analysis |
| **Lance versioning / time-travel demo** | Use Lance's built-in dataset versioning to show "knowledge at gate time vs now" | Reinforces the immutable-KB story |

## Known Phase-1 debt (non-blocking)

These were logged during the final branch review; none block the demo:

- `SOURCE_TABLES` constant in `common/source.py` is defined but not consumed by any external caller — remove or use.
- `react-router-dom` and `recharts` are in `03_frontend/package.json` but unused (Dashboard B deps added early) — prune once Dashboard B scope is settled.
- CSS token names carry `aml-` prefix inherited verbatim from the AML scaffold (`aml-red`, `aml-amber`, `aml-green`). Invisible to users; rename in a single CSS pass when convenient.
- `sentence-transformers` and `Pillow` are used-but-optional in `knowledge/kb.py` (guarded, fall back gracefully) but are not listed in `requirements.txt`. Add them (or split into `requirements-full.txt`) before publishing.
- README does not state that `01_installer/install.py` is a prerequisite. Add a "Quick start" note.
- No fresh-venv install test has been run — the first clean install on a new machine may surface missing transitive deps.

## Process note

All Phase 1 work landed directly on `main` (branch created from scratch, no existing main to protect). For Phase 2 work, use feature branches and PRs.

## UOB UI alignment correction

- Complete: UOB system font, blue controls, neutral panels, compact cockpit, and collapsed workflow diagram.
- Complete: standalone Knowledge base with external-source filtering and duplicate removal. Five unique original photographs are bundled.
- Complete: NiFi starter questions, composer, source-scoped answers, topology, history, and sample/live isolation.
- Complete: pinned CC BY 3.0 research package with eleven measured experiment rows, two original figures, source excerpt, and source XML. Offline extraction and checksums validate the package.

- 2026-10-22: bundled four additional licensed originals with checksums; Lance now exposes five unique reference photographs.
- Implemented predefined semantic context: [predefined context plan](semantic-context-plan.md), based on inspected Semantic Hub manufacturing fixtures and DOE evidence.

## Unified data v2

Implemented shared revision scope, independent observations, exact report links, issue history, and shared cockpit/canvas/review metrics. See [unified-data-v2.md](unified-data-v2.md) for source contracts, endpoints, validation, and remaining production limitations.

## Demo/Pilot foundation

Data mode, read-only canonical pilot imports, source readiness, native Workbench RO/RW enforcement, same-origin mutation checks, and authenticated actor audit are implemented. See [foundation runtime and security](foundation-runtime-security.md). Pilot review execution, source freshness acceptance, real connectors, and remote Workbench acceptance remain pending.


## Knowledge v3

See [knowledge-v3.md](knowledge-v3.md) for the pinned embedding contract, build-time extraction, scoped retrieval, conservative narration, and explicit OCR command. Normal preparation and runtime never initiate paid OCR.
