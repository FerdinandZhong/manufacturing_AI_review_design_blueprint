# User Guide

The Program Cockpit (Dashboard A) from the seat of a program manager / engineering lead. For the scripted presentation flow see [demo_storyline.md](demo_storyline.md).

## Getting in

After `python 02_backend/scripts/prepare.py` and `python start_app.py`, open **http://localhost:8100**. The cockpit loads the showcase program **PACK-ATLAS-01** (a new EV battery-pack NPI program) by default.

> The demo runs fully offline. With no LLM endpoint configured, agent findings and the gate narrative come from deterministic templates — the numbers, verdicts, and the gate recommendation are unaffected (they're computed, not generated). A live gate-review stream takes ~80s because each agent's LLM call times out to its template.

## What you see

**Stage tracker (top).** The lifecycle `REQUIREMENTS → DESIGN → ENGINEERING → VALIDATION → GATE_REVIEW → RELEASED`. PACK-ATLAS-01 is pre-seeded through VALIDATION; the gate review is the live step.

**Requirements / Design / BOM (left).** The program's five requirements (one per category: range, energy_density, thermal, safety, cost), their design specs, and the bill of materials — tabbed.

**Design-Risk panel (left).** The traditional-ML model's scores, ranked. The **thermal requirement shows HIGH (red)** — the model, trained on two historical programs, predicts thermal is risky. Below the list, the top-5 feature importances explain *why* (is_thermal and spec/margin dominate).

**Traceability matrix (center).** One row per requirement: requirement → design spec → test → verdict. Verdict cells are color-coded (PASS green, MARGINAL amber, FAIL red). The **cost requirement row is flagged as a gap** — it has a design spec but no test plan (coverage 4/5 = 0.8).

**Knowledge cards (right).** A multimodal retrieval panel. A thermal query surfaces a prior program's seeded assets — a **DesignImage** (thumbnail) and a **TestReport** — each tagged with its ontology class and the requirement it links to. This is knowledge reuse: "here's how a past program handled this thermal risk."

## Running a Gate Review

1. Click **Run Gate Review**. Five agent worker cards appear and stream to done in parallel:
   - **coverage** — every requirement traces to a design + test (flags the cost gap).
   - **testverdict** — summarizes DVP&R results (flags the MARGINAL thermal test).
   - **compliance** — checks EV-battery standards coverage (UN38.3, GB 38031, IEC 62660).
   - **designrisk** — explains the ML score, citing the numeric HIGH and the top feature.
   - **knowledgereuse** — cites a retrieved multimodal asset by ontology class + id.
2. A **recommendation badge** appears — **CONDITIONAL** for the showcase (amber): the program isn't a FAIL, but the MARGINAL thermal test + the coverage gap + any missing standard hold it back from a clean PASS. This value is code-computed and identical every run.
3. A narrative streams beneath the cards, summarizing the findings in prose.

## Making the gate decision

Once the review completes, the **Decision control** enables. Choose one:
- **APPROVED** — pass the gate.
- **APPROVED_WITH_CONDITIONS** — pass with follow-ups (the natural call for a CONDITIONAL).
- **REJECTED** — send it back.

Optionally add a rationale and your name. Submitting records the decision (writes an `annotations` row, finalizes the gate review, advances state to RELEASED) and the persisted result is shown back.

## Reading the corroboration story

The point of the demo: the **ML model (HIGH thermal risk)** and the **independent physics-style test bench (MARGINAL thermal test)** agree, from two entirely separate computations. The agent swarm doesn't decide anything — it *explains* and *retrieves*; the PASS/CONDITIONAL/FAIL call is a pure function of the data, and a human makes the final gate decision.

## Not in this dashboard (Phase 2)

Engineering-Ops (Dashboard B): traceability heatmap, change-request impact analysis, field-feedback → knowledge precipitation. See [TODO.md](TODO.md).


## Models portal and evidence previews

Use **Models** in the header to register an OpenAI-compatible narration endpoint (OpenAI, CAII, vLLM, or Ollama). Supply an alias, model identifier, API base URL (including `/v1` where required), and optional API key. Registration makes the model active. **Test** checks connectivity, **Edit** updates settings (a blank key retains the stored key), and **Use** activates a different model. Settings persist in SQLite; API responses mask keys. Without a usable endpoint, narration falls back to deterministic templates. Scores and gate recommendations remain computed by code.

The gate-review graph shows the supervisor dispatching five parallel specialists, converging on the code decision, then producing the gate narrative. Node states follow the review stream; the completed graph remains visible. Worker completion events retain the backend's deterministic ordering. Switching to Models preserves the cockpit and any active review.

Knowledge cards show larger previews, captions, program links, and search similarity. Click **Open asset & details** for a full-size schematic/photo or readable document, linked entity IDs, reuse guidance, and provenance. Filter by asset type and press Search to explore the library. Similarity measures retrieval relevance, not confidence in an engineering claim.

Thermal layouts are synthetic illustrative schematics, not measured thermal maps. Component photos use a bundled, attributed BMW i3 reference photograph, not photos of the synthetic programs. Source and license links are available in the viewer. Spec sheets are served as readable text. Run `python 02_backend/scripts/prepare.py` after updating the project to rebuild the Lance assets; the resulting library works offline.
