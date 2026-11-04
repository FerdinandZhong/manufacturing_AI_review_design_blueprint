# Vehicle NPI pilot-readiness plan

Assessment date: 2026-10-23. Status: foundation implemented and locally tested; remote Workbench acceptance and first live program remain pending.
Scope: one controlled manufacturing pilot, CAI Workbench-authorized users, read-only operational sources, human gate approval, and reproducible evidence.
Branch: `v2/pilot-readiness`.

Authorization decision: CAI Workbench is the authority for user and service access. Reuse its project/application access controls and supported machine-authenticated routes. Do not introduce a separate application login, user directory, or custom role-management system.

## Current implementation

Unified-data v2 is complete. Demo includes the baseline, expanded validation, and revised-design snapshots.
Their cockpit, semantic, and review metrics share deterministic snapshot identities.

Foundation mode and access controls are implemented locally:

- Demo and Pilot preparation/runtime paths are separate. Pilot cannot seed, train, score, run the demo bench, or substitute samples.
- A controlled read-only canonical import provider validates keys, units, revision joins, timestamps, provenance, and content identity.
- Source status and review readiness are separate. Pilot freshness is explicitly not checked; pilot review execution remains unavailable.
- Native Workbench identity crosses a configured ingress boundary and a signed loopback hop. RO/RW is enforced on the backend.
- Same-origin mutation checks, restricted header forwarding, and trusted actor audit apply to UI and MCP API calls.
- The UI shows mode, source readiness, provenance, and native permission. Pilot shows inspected source records rather than Atlas data.
- MCP authentication documentation uses a Workbench API key with Application audience. New MCP tools remain out of scope.

See [foundation runtime and security](foundation-runtime-security.md) for configuration, the canonical source contract, and the trust boundary.
Local tests do not establish platform native-header sanitization, actual proxy peer ranges, real key acceptance, or operational source authenticity.
No remote deployment or real source credential was used for this milestone.

Remaining preparation work includes a pinned dependency release, fresh-runtime installation, broader smoke acceptance, and remote restart/restore checks.
Guardrail cards, one live connector, and expanded MCP tools remain later phases.

## Target experience

```text
Approved source adapters --> normalized records + source snapshot --+
                                                                   |
Versioned semantic package --> fixed joins and engineering rules ---+--> review --> human decision
                                                                   |      |
Lance references ------------> scoped evidence + provenance --------+      +--> AI explanation
                                                                          |
Workbench authorization + backend guardrails <-----------------------------+
                  |
          same backend exposed through UI and MCP
```

Keep the cockpit as the primary workspace. Add a program selector, explicit Demo/Pilot mode, source health, and snapshot timestamp.
A scenario card should select its context and move focus to the explanation controls. Show the selected question beside the answer.
Keep images in Knowledge base and technical/reference details collapsed. Put warnings beside affected results rather than adding more summary panels.
Persist review status so reconnecting does not require restarting a review. Show missing-data and stale-source states explicitly.

## 1. Real source compatibility

### First supported pilot path

Implement a source-provider interface behind the current accessors. Keep CSV as a demo/import provider.
Prioritize approved Impala views over Iceberg tables for the first Cloudera pilot. Add direct Iceberg access only if the target catalog/authentication requires it.
Avoid building many connectors before the first real source is confirmed.

Separate three data paths:

| Path | Scope | Required behavior |
|---|---|---|
| Engineering records | Programs, requirements, designs, BOM, suppliers, test plans | Read-only, allowlisted tables/views, parameterized filters, bounded results |
| Actual test evidence | Lab/MES/QMS result records and reports | Preserve measured value, unit, method, revision, timestamp, source identity, and provenance |
| Documents and images | Approved object storage or controlled uploads | Build-time ingestion, content checksums, licensing/access metadata, versioned Lance dataset |

NiFi monitoring remains a fourth, separate operational view. If NiFi supplies evidence, use an approved ingestion output with a data contract.
Do not mistake a healthy pipeline or queued FlowFiles for available engineering test results.

Define keys, join cardinality, units, revision scope, null rules, and ownership for every mapped dataset.
Reject duplicate keys, unknown units, broken references, or mismatched revisions before a pilot review.
Snapshot source identifiers and extraction time with each review. Replaying that snapshot must reproduce its engineering decisions.
Replace process-lifetime CSV caching with an explicit refresh/snapshot policy; show freshness in the UI.

Introduce explicit `demo` and `pilot` preparation profiles. Pilot mode must never generate synthetic source records, run the demo bench, or substitute sample data after a live failure.
Actual evidence supplies pilot measured values; approved code rules calculate derived verdicts. Preserve source-native verdicts separately when they also exist.
Do not serve the synthetic-trained risk model as a calibrated pilot prediction. Show risk as unavailable until a domain-approved model passes validation.
Keep the deterministic Atlas reference scenario available in Demo mode.

Parameterize semantic packages by program/schema/snapshot. Reuse reviewed definitions; unknown program mappings must return unavailable, not Atlas context.

Acceptance: connect one real program, reconcile selected rows with the source owner, prove source writes are impossible, and replay one review from a fixed snapshot.

## 2. Predefined guardrails

Reuse UOB's card presentation: task selector, Input/Tool/Output sections, title, summary, expandable definition, Apply, Flag/Block, and a saved revision.
Provide a compact Try a check panel and a visible enforcement state: enforced by code, model advisory, inactive, or not checked.
Do not copy UOB's configuration-only tool cards as if they provide protection.

Suggested tasks: Engineering review, Semantic explanation, Knowledge retrieval, and NiFi inspection.

| Card | Stage | Enforcement |
|---|---|---|
| Approved program and source scope | Tool | Code block on unauthorized source/program |
| Read-only operations | Tool | Code block on source or NiFi mutation |
| Source freshness and schema validity | Input/tool | Code blocks affected pilot review when mandatory evidence is invalid |
| Valid units and revision joins | Tool | Code rejects incompatible calculations |
| Synthetic versus actual evidence | Tool/output | Code separates origins and prevents synthetic substitution |
| Citation and asset identity | Output | Code validates selected evidence IDs and locators |
| Secret exposure | Input/output | Deterministic redaction/checks; block detected disclosure |
| Unsupported compliance or safety claim | Output | Advisory language check; authoritative decision remains code/human |
| Prompt injection in retrieved material | Input | Treat source text as data; optional model flags; fixed tools and permissions remain authoritative |
| Unperformed action claims | Output | Compare claims with recorded tool outcomes; flag/reject unsupported status |

UOB uses a guard model for some blocking decisions. This project states that an LLM must not control decisions or control flow.
Therefore model-based checks remain advisory by default. Changing that contract requires a separate explicit architecture decision.
Required authorization, mutation, unit, and source-validity controls cannot be switched off through a card toggle.
Configurable actions apply only to policies that are allowed to vary.

Add catalog/config/test APIs, optimistic revision checks, and enforcement hooks in shared backend services.
Store policy revision, stage, rule IDs, outcome, and request/review correlation. Do not store credentials or unrestricted prompt content.
Apply the same controls to direct API calls and MCP calls. UI-only checks are insufficient.

Acceptance: blocked requests make no protected source/model call; required controls survive disabled optional cards; failed mandatory validation cannot yield a successful review.

## 3. MCP upgrade

Retain the thin HTTP-adapter architecture. MCP must not import the backend, read SQLite/Lance directly, or implement duplicate engineering formulas.

| Proposed tool | Backend mapping |
|---|---|
| `get_semantic_model` | Existing GET `/semantic/model` |
| `get_semantic_context(question_id)` | Existing GET `/semantic/context` |
| `explain_semantic_context(question_id, narration, include_images)` | Existing POST `/semantic/explain`; mark model/network use explicitly |
| `get_reference_measurements(source_id, experiment_id, limit, offset)` | New bounded JSON endpoint; retain CSV download for users |
| `get_nifi_status(mode)` | Existing `/nifi/config` + `/nifi/snapshot`; credentials excluded |
| `list_source_status` | New readiness/provenance endpoint |
| `get_guardrail_catalog` / `get_guardrail_status` | New catalog/read-only effective-policy endpoints |

Extend `search_knowledge` with external-only/source/type filters and pagination as needed. Preserve existing defaults for compatibility; use external-only for pilot reference browsing.
Align semantic and KB asset IDs. The current BMW semantic alias and stored KB asset IDs need a stable shared identity before new generic content tools use them.
Keep original-content tools for images/text; add source locators and applicability metadata.

Apply read-only/non-destructive annotations consistently. Keep `trigger_gate_review` explicitly mutating and idempotent; require authorized scope.
Do not expose gate approval, model credentials, guardrail administration, or source configuration through general agent tools.
Add API capability/version negotiation, bounded responses, stable error codes, transport timeouts, and redacted errors.
Ship the MCP package from a tested release or commit rather than a floating main branch for pilot deployments.

Acceptance: a separate stdio process discovers a program, obtains semantic context, reads a source figure and experiment row, inspects NiFi, and reads a review.
Verify equivalent authorization/guardrails through UI/API/MCP and no writes from read tools. Verify the actual machine-authenticated Workbench route, not only localhost.

## 4. AMP preparation and deployment

Keep one Workbench Application serving React and proxying the loopback backend. Keep build tasks separate from application startup.
Use CAI Workbench project/application permissions and supported ingress authentication. Validate the target workspace’s actual UI and machine-access behavior. Do not infer per-action permissions from project role labels. Backend read-only source restrictions and engineering guardrails remain independent of identity management.

Preparation changes:

1. Unify direct AMP tasks and `prepare_application.py` around the same preparation contract.
2. Select Demo or Pilot mode before any generation or artifact build.
3. Add a Python 3.11 tested dependency lock, explicit Pillow test dependency, and a selected/pinned embedding strategy.
4. Bundle and validate research/photo assets, attribution, hashes, semantic definitions, and versioned KB outputs.
5. Pin the MCP release and verify it from a separate process.
6. Add smoke checks for semantic questions, source states, guardrails, NiFi sample/live separation, and original asset content.
7. Make preparation idempotent without overwriting pilot measurements, model registrations, reviews, or source files.
8. Add readiness distinct from liveness, artifact schema/version checks, and restart regression tests.
9. Exercise rapid restart handling without relaxing genuine port-collision detection.
10. Produce a release manifest: code revision, dependencies, semantic/policy versions, source snapshot, model version, and KB version.

Pilot runtime controls:

- CAI Workbench-managed user and service access; no separate application roles or login. Keep the Application private and use supported Workbench authentication for MCP.
- Record the Workbench-authenticated actor in audit events when the supported integration supplies verified identity. Never trust caller-supplied identity headers or label a typed reviewer name as authenticated identity.
- Scope the pilot Application to the intended Workbench-authorized participant group. Verify access to review and configuration actions through the deployed ingress.
- Allowlisted inference/source endpoints and trusted TLS; credentials remain in approved secret storage and never in MCP payloads.
- Restricted browser origins and CSRF protection where cookie authentication applies.
- One application replica initially; bounded review concurrency, SQLite lock handling, backup and restore checks.
- If multiple replicas or higher write concurrency are required, migrate the operational store before expanding deployment.
- Request/review correlation, latency and connector-error metrics, policy outcomes, and redacted audit logs.
- Preserve source/semantic/policy snapshots with review evidence; record missing evidence explicitly.

Fresh-deployment acceptance: install from a clean project and pinned revision, prepare successfully, open authenticated UI, run demo and live-source checks, call MCP from its real host, restart, and restore a backup.
A local manifest pass is necessary but does not prove this remote acceptance.

## Delivery order and exit criteria

| Phase | Deliverable | Exit criterion |
|---|---|---|
| 1 — Foundation (implemented locally) | Mode separation, canonical source contract, native Workbench access boundary, snapshot identity | Local regression and mocked auth tests pass; remote ingress/key acceptance remains pending |
| 2 — First live program | One connector, actual test evidence, parameterized semantic mapping, cockpit source status | Source-owner reconciliation and repeatable review succeed |
| 3 — Guardrails and MCP | Enforced predefined cards, shared policies, updated tools | Direct API and MCP cannot bypass mandatory checks |
| 4 — AMP qualification | Pinned build, parity smoke checks, private deployment, restart/restore evidence | Clean Workbench deployment and remote agent acceptance pass |

Keep the existing demo usable throughout. Start with one program and one real engineering source rather than expanding connector count.
Before live integration, obtain: source/view names, authentication route, field/unit/revision mapping, representative records, Workbench project/application access configuration, and intended pilot concurrency.
These inputs are needed for live integration, not for implementing the adapter contracts and demo/pilot separation.

## Source references

- [Source adapter](../02_backend/common/source.py)
- [Current preparation](../cai_integration/prepare_application.py)
- [AMP metadata](../.project-metadata.yaml)
- [MCP implementation](../mcp_server/npi_mcp/server.py)
- [UOB predefined guardrails](../../uob-ai-data-operations-workspace/docs/plans/predefined-guardrails.md)
- [Cloudera Applications documentation](https://docs.cloudera.com/machine-learning/cloud/applications/topics/ml-applications-c.html)
