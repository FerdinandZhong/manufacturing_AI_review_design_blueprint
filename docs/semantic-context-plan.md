# Predefined semantic context implementation plan

Status: implemented, 2026-10-22. Graph discovery, exact NPI joins, five original photographs, eleven verified published experiment rows, two original study figures, source excerpt, context inspection, and deterministic explanation fallback are implemented.

## Recommendation

Keep battery-pack NPI as the primary story. Prebuild a small, versioned context package and display its relationships, evidence, and AI inputs.
Do not add a builder, publishing workflow, external semantic service, or automatic schema discovery.
Use Semantic Hub's manufacturing sample as a design reference. Its records are synthetic and cannot satisfy the request for real measurements.

## Implemented behavior and resolved screenshot error

`knowledge/semantic_context.yaml` defines concepts, joins, metrics, applicability rules, and four predefined questions.
The original scaffold required a missing research manifest and CSV for every request. Context discovery now works independently of that package.
Missing or invalid research sources disable the research question only. Available photographs and the NPI graph remain usable.
The bundled study supplies eleven source-verified experiment rows, two original figures, and a readable source excerpt.
ResearchFigure and ResearchDocument are registered ontology classes, and the assets are ingested into Lance at build time.
External measurements never replace Atlas test values, risk scores, or gate decisions.

## Inputs inspected in Semantic Hub

| Input | Verified contents | Reuse here |
|---|---|---|
| `fixtures/sectors/v1/manufacturing/manifest.json` | Seed 8100; 12 assets, 240 sensor readings, 12 work orders; no downloaded external records | Origin labels and source manifest pattern; retain this origin if importing a separate scenario |
| `serving/draft.ossie.json` | Field definitions, two asset_id relationships, downtime metric | Explicit keys, table grain, units, and saved metric formulas |
| `serving/assets.csv` | Asset ID, site, line | Optional factory-maintenance scenario; no join to Atlas exists |
| `serving/sensor_readings.csv` | Timestamp, air/process temperature K, rpm, torque Nm, tool wear minutes | Unit-aware context and time-grain examples |
| `serving/work_orders.csv` | Work order ID, asset ID, status, downtime minutes | Deterministic aggregate and join demonstration |
| `serving/documents/SYN-WO000.md` and peers | Authored synthetic maintenance notes | Example exact document-to-work-order link; not real engineering evidence |
| `docs/demo-inputs/manufacturing-real/` | Real DOE guide excerpt and source/page/checksum manifest | Source-located prose, thermal images, and applicability boundaries |

The downtime expression is `SUM(work_orders.downtime_minutes)`. The source pack totals 312 minutes.
Its name, `planned_downtime_minutes`, does not apply a status filter. Do not infer a filter from the name.
Joining readings and work orders before summing can multiply downtime. Aggregate at work-order grain before combining results.
Do not load `evaluation/reference.json` into AI context. It is evaluation-only.

The DOE excerpt maps pages 4/5 to original physical PDF pages 51/52 for preventive/predictive maintenance.
Excerpt pages 8/9 map to original physical pages 64/65 for thermal imagery and bearing examples.
Those images provide general condition-monitoring context. They do not measure the synthetic assets or Atlas cells.
Confirm figure-specific reuse terms before bundling extracted images; retain the complete attribution and page mapping.

## Prebuilt context package

Create a read-only package with these records:

| Record | Required fields |
|---|---|
| Entity definition | ID, source table, primary key, grain, origin |
| Concept | ID, label, aliases, definition, unit constraints |
| Relationship | Source/target, exact-key or curated-reference type, rule, cardinality, rationale |
| Metric | ID, deterministic function/SQL, unit, grain, filters, missing-data rule |
| Evidence | Lance asset ID, source ID, author, license, checksum, page/figure locator, modality |
| Evidence link | Concept ID, asset ID, optional source experiment ID, applicability, review status |
| Demo question | ID, fixed intent, allowed relationships, metric IDs, evidence IDs, expected facts |

Keep native identities separate: NPI requirement IDs, external source IDs, and optional manufacturing asset IDs.
Use `exact_key` for real foreign-key joins. Use `curated_reference` for photographs and concept associations.
A real photograph is not an Atlas part record. Never create an equality join based on a similar caption.

```text
NPI CSV + SQLite ---> deterministic joins and metrics ---+
                                                       |
Predefined concepts ---> approved relationship paths ---+--> context packet --> AI explanation
                                                       |          |
Lance image/document bytes ---> source-located evidence-+          +--> citations and input inspector
```

## Implementation sequence

1. Decouple context discovery from evidence availability.
   Load graph, concepts, and structured facts without opening a research manifest.
   Return per-source states: available, missing, or invalid checksum.
   Disable only questions that require missing evidence; show the specific missing source.
   Separate context metadata routes from execution routes.

2. Complete the NPI semantic contract.
   Define Program, Requirement, DesignSpec, Part, TestPlan, TestResult, and RiskScore grains and exact joins.
   Preserve thermal HIGH, thermal MARGINAL, and gate CONDITIONAL.
   Add pack architecture and cell construction concepts for the five available original photographs.
   Keep thermal response, venting, and applicability concepts for the later research package.
   Add units and source/target applicability to every evidence relationship.

3. Prepare real multimodal evidence at build time.
   Reuse the pinned photographs now in `data_generation/assets/references/manifest.json` and the existing BMW image.
   Add the DOE excerpt only as general maintenance context after checking reuse terms.
   For the quantitative battery story, acquire a source containing figures and measured experiment tables.
   Transcribe rows with source_id, experiment_id, method, chemistry, unit, table locator, and reviewer status.
   Link a figure to rows only when the source explicitly identifies those experiments.
   Validate checksums, units, row counts, and table transcription before enabling that question.
   Add ResearchFigure/ResearchDocument classes when those assets are actually ingested.
   Run ingestion offline from bundled files during `prepare.py`; do not download at runtime.

4. Build a read-only demonstration page.
   Show three areas: predefined questions, relationship graph, and the selected evidence/facts panel.
   Distinguish exact joins from curated reference links with labels and a legend.
   Clicking a node shows its definition, grain, origin, source rows, or original image/page.
   Add an AI context inspector showing selected facts, definitions, relationship path, and citations.
   Display model-generated prose separately from code-computed facts.
   Show whether an image was passed to a vision-capable model or only its curated caption was used.
   Keep the UOB typography, blue controls, neutral panels, and compact tables.

5. Add bounded explanation behavior.
   Select a fixed question route; compute facts and select evidence before calling the model.
   Give the model only the resulting context packet and optional selected images.
   Require citations to supplied asset IDs and locators; flag unknown citations.
   Retain deterministic explanations for offline or unavailable-model mode.
   Never use model text to alter verdicts, metrics, source data, or routing.

6. Validate and package the demo.
   Test joins, metric grain, unit rules, missing sources, corrupt assets, and citation references.
   Test the graph and image viewer at desktop and mobile sizes.
   Verify the full Atlas gate regression and reproducible source checksums.
   Keep the semantic-hub manufacturing scenario optional and isolated until explicitly included.

## Predefined questions and acceptance results

| Question | Inputs | Expected behavior |
|---|---|---|
| Why does Atlas thermal risk need attention? | Requirement, design, bench result, ML score | Explain independent HIGH and MARGINAL signals; no external image is treated as a measured Atlas result |
| What do the real photographs show about battery packaging? | Pack/cell concepts and five attributed originals | Show cell, module, enclosure, and vehicle placement references with citations; avoid unsupported material/performance claims |
| Can these photographs validate Atlas thermal performance? | Evidence-link applicability and NPI metric definitions | Explain that photographs provide reference context, not a thermal test or compliance result |
| What do published tests show about thermal response and venting? | Verified research tables, figures, source locators | Enabled only after the real measurement package passes validation; same-source joins remain inspectable |
| Optional: how do maintenance records and thermography complement one another? | Separate manufacturing fixture plus DOE evidence | Report synthetic work-order metrics separately from real maintenance guidance; no invented vibration field or failure forecast |

The first deliverable should make the graph and available-image questions usable without a paper dependency.
The second deliverable should add verified real experiment rows and figures for the stronger quantitative multimodal story.
This avoids presenting photographs alone as the requested real structured-plus-unstructured measurement dataset.

## References inspected

- [Semantic Hub manufacturing manifest](../../semantic-hub/apps/helios-ds-generation/fixtures/sectors/v1/manufacturing/manifest.json)
- [Manufacturing semantic definition](../../semantic-hub/apps/helios-ds-generation/fixtures/sectors/v1/manufacturing/serving/draft.ossie.json)
- [Manufacturing real-document guidance](../../semantic-hub/docs/manufacturing-real-document-sources.md)
- [DOE provenance manifest](../../semantic-hub/docs/demo-inputs/manufacturing-real/manifest.json)
- [Local image manifest](../02_backend/data_generation/assets/references/manifest.json)
