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

**Knowledge base.** Open the sidebar tab to browse balanced, scoped evidence. Filter direct demo evidence, historical evidence, or attributed external references.

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

The point of the demo: the **ML model (HIGH thermal risk)** and the **independent observation-based synthetic test bench (MARGINAL thermal test)** agree, from two entirely separate computations. The agent swarm doesn't decide anything — it *explains* and *retrieves*; the PASS/CONDITIONAL/FAIL call is a pure function of the data, and a human makes the final gate decision.

## Not in this dashboard (Phase 2)

Engineering-Ops (Dashboard B): traceability heatmap, change-request impact analysis, field-feedback → knowledge precipitation. See [TODO.md](TODO.md).


## Models portal and evidence previews

Use **Models** in the sidebar to register an OpenAI-compatible narration endpoint (OpenAI, CAII, vLLM, or Ollama). Supply an alias, model identifier, API base URL (including `/v1` where required), and optional API key. Registration makes the model active. **Test** checks connectivity, **Edit** updates settings (a blank key retains the stored key), and **Use** activates a different model. Settings persist in SQLite; API responses mask keys. Without a usable endpoint, narration falls back to deterministic templates. Scores and gate recommendations remain computed by code.

The gate-review graph shows the supervisor dispatching five parallel specialists, converging on the code decision, then producing the gate narrative. Node states follow the review stream; expand **Agent workflow** to inspect the graph. Worker completion events retain the backend's deterministic ordering. Switching to Models preserves the cockpit and any active review.

Knowledge base lists original source material with previews, attribution, source links, and license links. Reused copies appear once.
The current collection contains eight unique assets, including five original photographs: BMW i3, two Nissan Leaf pack views, an 18650 cell, and a Leaf cutaway. It is reference material, not evidence from the synthetic Atlas program.
Generated reports and schematics are explicitly labelled demo evidence. The evidence-type selector can restrict the collection to external references.
The Semantic context tab also includes eleven published LMO-cell experiments, two original study figures, and a source excerpt. Figure 13 links explicitly to experiment 7. Figure 2 has no numbered experiment link.


## NiFi reader

The sidebar opens Program Cockpit, Knowledge base, Semantic context, NiFi reader, and Models. The header search finds workspace pages.

1. Open **NiFi reader** and select a starter question.
2. Ask for current status, topology, processor health, or recent bulletin metadata.
3. Select a topology processor to inspect its connections.
4. Open **Connection settings** and select **Live NiFi** for the configured process group.
5. Submit another question to fetch a new snapshot. Use **Recent questions** to revisit a prompt.

The reader uses deterministic question routing. It does not generate arbitrary answers or execute flow changes.

Live mode requires backend configuration. Open **Connection settings** for the required environment variables.
A failed live request shows an error. It never substitutes sample data.
The reader shows direct child processors, connections, group metrics, and scoped bulletin metadata.
Nested groups and ports remain unexpanded. Bulletin messages stay in NiFi because they can contain sensitive property values.
These snapshots do not provide historical logs, modify processors, or feed the NPI decision pipeline.


### Explore predefined semantic context

1. Open **Semantic context** from the workspace navigation.
2. Select an available question.
3. Select graph nodes to inspect their source records and join keys.
4. Open **Knowledge base** to inspect original images, attribution, and licenses.
5. Expand the context inspector to inspect selected facts, relationships, and citations.
   Published measurements and reference definitions stay collapsed until opened.
6. Choose the offline explanation or the configured model.

Solid graph edges show explicit identity or source-locator links. Dashed edges show curated reference associations.
Photographs provide visual context. They do not identify Atlas parts or validate thermal performance.
Missing or invalid research disables its question while the graph and available photographs remain usable.
The model can narrate facts. It cannot change test verdicts, risk scores, or the gate decision.

## Engineering revisions

Use the Engineering revision selector to switch the cockpit, semantic canvas, and knowledge collection together. Expanded validation is the default. Original baseline preserves the original demo. Revised design closes the test gaps and verifies the cooling corrective action.

Open Engineering details for issue history, action completion, and quantity-weighted BOM totals. Knowledge base offers evidence-type filters. Generated reports are direct demo evidence. External materials provide context only. See [the unified data contract](unified-data-v2.md).

## Demo/Pilot foundation

Data mode, read-only canonical pilot imports, source readiness, native Workbench RO/RW enforcement, same-origin mutation checks, and authenticated actor audit are implemented. See [foundation runtime and security](foundation-runtime-security.md). Pilot review execution, source freshness acceptance, real connectors, and remote Workbench acceptance remain pending.
