# Unified engineering data

The cockpit, semantic canvas, and review workers use the same engineering scope.
A scoped program key selects a program revision. The canonical program ID remains `PACK-ATLAS-01`.

| Transport program key | Revision | Requirements | BOM rows | Plans | Observations | Computed gate |
|---|---|---:|---:|---:|---:|---|
| `PACK-ATLAS-01` | baseline | 5 | 5 | 4 | 32 | CONDITIONAL |
| `PACK-ATLAS-01@atlas-v2` | expanded validation | 30 | 48 | 24 | 192 | CONDITIONAL |
| `PACK-ATLAS-01@atlas-v3` | revised design | 30 | 48 | 30 | 240 | PASS |

The original baseline preserves the 80% coverage, MARGINAL thermal result, and HIGH thermal ML band.
Its original numeric targets remain a legacy regression fixture.
Expanded revisions use engineering targets, explicit units, and acceptance direction.
The thermal headroom target is 10 degC. The cost target uses lower-is-better acceptance.

The revised design changes cooling headroom, closes coverage gaps, and records a verified corrective action.
Its independent follow-up observations support PASS bench results.
The small historical ML model can still rate thermal requirements HIGH.
The gate formula does not include ML risk. The UI reports these independent results separately.
This model is a deterministic demonstration, not a validated production predictor.

## Data flow

```text
Pinned source revisions + independent observations
                        |
                 deterministic bench
                        |
                 SQLite scoped results
                        |
                shared metric service
                 /       |       \
             cockpit   canvas   review workers
                        |
              immutable review evidence

Canonical report registry -> build-time Lance assets -> scoped knowledge search
External research --------> reference context only
```

`generate_snapshots.py` uses seed 42 and produces byte-identical JSON source files under `data/raw/snapshots/`.
Runtime access only reads these files. `prepare.py` generates sources and builds derived artifacts.
Observations never read design values. Each observation records its unit, condition, replicate, run, and fixed timestamp.
The bench averages each plan's eight observations. It rejects missing observations and incompatible units.
PASS requires a directional margin of at least 10%. MARGINAL requires a nonnegative margin.

Snapshot IDs hash canonical source payloads. Runtime readers verify each revision's content hash.
The baseline identity hashes its authoritative CSV tables and its pinned observation fixture.
Source and metric contract versions are pinned in revision payloads.
Result IDs include the scoped program key. SQLite isolates results, scores, and reviews with that same key.
Stored results and scores carry snapshot IDs. Metrics reject stale results and scores.
Reviews persist canonical program, revision, and snapshot IDs. Evidence records use that snapshot as their data version.

`engineering.metrics.summary` defines planned coverage, executed coverage, attention counts, risk counts, missing scores,
quantity-weighted BOM cost and mass, open issues, action completion, and observation evidence coverage.
Every ratio includes its denominator. Observation evidence coverage means plans linked to seeded observations.
It does not mean certified supporting evidence or regulatory approval.

The traceability matrix preserves every linked design and test ID.
Its verdict uses the worst available test verdict. ML features aggregate all linked BOM items with quantities.
Scoring includes untested requirements. Training excludes requirements without labels.
Only Orion and Vega provide historical training data. Revised Atlas records never enter training.

## Evidence scope

The canonical BMW photograph ID is `REF-bmw-pack`. Lance and the semantic canvas use this same ID.
Generated reports contain exact source plan standards, observation IDs, aggregate values, verdicts, and snapshot identities.
Direct demo evidence applies only to its exact revision. It is explicitly synthetic.
Historical demo evidence uses the Orion and Vega scopes. External references cannot change deterministic decisions.
Knowledge search filters scope before display. Its balanced default includes direct, historical, and external evidence.
An evidence-type selector provides narrower views. The semantic canvas keeps its compact layout.

## API and checks

- `GET /api/scenarios` lists available revisions and identities.
- `GET /api/programs/{key}` supplies the shared metrics, identity, issue list, and revision history.
- `GET /api/programs/{key}/snapshot` exposes observations and their conditions.
- Engineering query datasets include `observations`, `issues`, and `history`.
- Semantic context and explanation routes accept `program_id` as the scoped program key.
- Knowledge search accepts `program_id` and `evidence_kind`.

Run `python 02_backend/scripts/prepare.py` after changing source generation.
Backend pytest automatically isolates SQLite, model, and Lance artifacts through `tests/conftest.py`.
Run `npm run build` and `npm run lint` in `03_frontend`.

Production connectors, real laboratory data, credentials, validated acceptance protocols, and larger historical training cohorts remain future work.
Source accessors provide an explicit contract for those integrations. No live connector is assumed or configured.
