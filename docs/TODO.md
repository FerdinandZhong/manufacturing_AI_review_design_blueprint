# TODO

## Current status

**Phase 1 complete.** All 13 implementation tasks (Tasks 0–12) plus a final whole-branch review are merged on `main` (21 commits). The 36-test suite is green. The showcase program `PACK-ATLAS-01` is fully seeded and the marquee Gate Review runs deterministically end-to-end.

Run today:
```bash
python 02_backend/scripts/prepare.py   # idempotent bootstrap
python start_app.py                    # → http://localhost:8100
```

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
