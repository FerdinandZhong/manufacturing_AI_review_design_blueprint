# Demo/Pilot foundation and Workbench access

This milestone separates demonstration data from controlled pilot imports.
It integrates native Workbench permissions at the application boundary.
It does not establish remote deployment acceptance or source-owner approval.

## Runtime profiles

`NPI_DATA_MODE=demo|pilot` selects the data profile.
It is independent of `NPI_APP_MODE=prod|dev`, which selects frontend serving.
Local Demo retains all three Atlas revisions.

Pilot preparation validates a read-only canonical import and initializes a separate operational database.
It never generates synthetic CSV or snapshots, runs the demo bench, trains/scores the demo model, or builds the demo Lance package.
The direct AMP generation task skips its work in Pilot mode.
The preparation wrapper and AMP tasks share these profile checks.
Calling the guarded generators or bench directly in Pilot mode fails explicitly.

Set `NPI_SOURCE_PROVIDER=canonical_import` and `NPI_PILOT_SOURCE=/approved/path/snapshot.json`.
A relative import path resolves against the project root.
The provider reads at most 10 MiB and 10,000 rows per table.
It validates every read and never writes the source.
Missing or invalid data returns explicit source-unready status. It never resolves to CSV or sample data.

Pilot defaults to `data/pilot/npi.db` for operational state.
Configure a different path with `pilot.ops_db_path` when required.
The application rejects a path that resolves to the Demo database.
Pilot source observations remain separate from operational computed results.
Pilot summary and matrix endpoints expose structural links and source counts only.
Risk, computed test attention, executed acceptance coverage, required-standard coverage, and gate recommendations return null with unavailable status.
Operational rows cannot enable these metrics or produce a pilot gate verdict.

`GET /api/runtime/status` reports data mode, authentication mode, trusted actor, source readiness, and review readiness.
Source readiness means structural validation only. Freshness is explicitly `not_checked` at this milestone.
The UI displays extraction time and provenance. Source-owner reconciliation and a freshness policy remain pending.

Pilot displays imported requirements and observation records.
Pilot reviews, computed verdicts, synthetic risk, Atlas semantics, and demo knowledge return unavailable.
Sample NiFi is disabled. Live NiFi failures never substitute samples.
Model configuration remains protected by native RW permission.

## Canonical import contract

The schema version is `npi-pilot-v1`.
The root must contain `source_kind: actual`, `source_id`, `revision_id`, `extracted_at`, `provenance`, and `program`.
Declaring `actual` is a source-owner assertion, not independent proof of measurement authenticity.
Do not import Atlas demo identities as operational programs.

`program` requires `program_id`, `name`, `vehicle_platform`, `stage`, and `gate_status`.
The following arrays are mandatory, including when empty:

| Table | Unique key | Required links and values |
|---|---|---|
| requirements | req_id | category, text, priority, status, positive finite target_value, unit, acceptance_direction |
| design_specs | spec_id | req_id, finite value, compatible unit, parameter, version |
| bom_items | part_id | spec_id, supplier_id, name, nonnegative finite qty/unit_cost/mass_kg |
| suppliers | supplier_id | name, region |
| test_plans | test_id | req_id, method, unit, matching target_value and acceptance_direction |
| observations | observation_id | test_id, finite measured_value, compatible unit, timezone-aware recorded_at |

Every row requires matching `program_id`, `revision_id`, `source_id`, and nonempty `provenance`.
Canonical program and row keys contain letters, digits, dots, underscores, and hyphens, with a maximum length of 128.
Duplicate keys, broken references, incompatible units, and revision mismatches make the source unready.
Unknown units require an explicit contract update. The supported unit list is `common/providers.py:UNITS`.
Preserve optional `source_native_verdict` on observations. The application does not turn it into a computed pilot verdict.
The snapshot identity hashes validated canonical source content. Extraction time and provenance participate in that hash.

## Native Workbench trust boundary

Workbench remains the sole user directory and permission authority.
The Application must remain private with authentication enabled.
Native `REMOTE-USER` and `REMOTE-USER-PERM` supply the actor and RO/RW permission.
No application login, user database, or custom role mapping exists.

```text
Private Workbench Application ingress
  native user + RO/RW (platform must sanitize caller identity headers)
                |
Frontend socket peer matched against configured proxy CIDRs
  reject duplicate/underscore native identities
  strip caller internal identity, credentials, and forwarding headers
  sign actor + permission + method + path/query + auth kind + Origin
                |
127.0.0.1 backend, signed process-owned hop proof
  require proof and loopback peer before trusting identity
  native RO -> reads and nonpersisting narration only
  native RW -> reviews/configuration/decisions, subject to CSRF and mode checks
                |
SQLite audit: authenticated actor, permission, route, outcome, status
```

Set `NPI_AUTH_MODE=workbench` explicitly for deployment.
Workbench domain, project, application, task, or `/home/cdsw` markers default to this policy.
A locally assigned `CDSW_APP_PORT` alone is not identity evidence.
Pilot also defaults to Workbench authorization even outside the platform.
The application refuses `local_demo` authorization in Pilot mode or detected Workbench environments.
Local Demo binds loopback and labels its explicit development actor `local-demo`.

Standard Workbench deployment resolves these values without setup input:

1. The origin is `https://vehicle-npi-platform.<CDSW_DOMAIN>`. A renamed app supplies `NPI_APP_SUBDOMAIN`; a custom URL uses `NPI_PUBLIC_ORIGIN`.
2. Trusted proxy peers default to `127.0.0.1/32,::1/128`, matching the loopback-only listener. `NPI_TRUSTED_PROXY_CIDRS` can override these for a custom ingress.

Empty overrides use the defaults. Invalid origins and untrusted peers reject protected requests.
Do not use arbitrary forwarded headers to discover the trusted peer.
Both Uvicorn listeners disable proxy-header rewriting.
The frontend and backend bind loopback. Workbench must reach the frontend through its private application proxy.
The process creates a fresh internal hop secret and supplies it only to its child backend.
This transport proof is not an application user credential or another login system.
It does not defend against a compromised process or a project owner who can change code and read process memory.

Do not expose the backend port as another Application.
Remote acceptance must verify the actual socket peer and Workbench's sanitization of supplied native identity headers.
The application cannot prove that platform behavior from local tests alone.

## Mutation checks and audit

Every persisted review, SSE review stream, test-bench execution, model configuration action, and decision requires RW.
The existing review SSE uses GET but remains a mutation under this policy.
Semantic explanation POST narrates without persisting state and remains available to RO in Demo mode.
NiFi reads never mutate NiFi.

Cross-origin mutations fail even when a caller adds an arbitrary Bearer header.
Browser writes require the configured same Origin, or a matching Referer plus the application request marker for GET streams.
Cross-site Fetch Metadata also fails. No permissive CORS middleware is installed.
Originless machine requests are accepted only after the native Workbench ingress identity and internal proof pass.
Bearer and Cookie credentials terminate at the frontend and never enter backend audit payloads.

Audit records contain actor, native permission, method, route, status, and outcome.
The application records verified authorization denials when the audit store is available.
An authorized mutation fails closed when it cannot record its audit attempt.
SSE audits say `stream_accepted`; they do not claim completion before streaming finishes.
Persisted review status remains the authority for review completion.
Typed adjudicator names never override the authenticated Workbench actor.

## Verification and remaining acceptance

MCP package installation remains part of preparation. Run `python -m pytest mcp_server/tests -q` separately during release verification.
Operational preparation never launches the demo-seeding MCP test suite in Pilot mode.

Local tests mock native ingress, peer CIDRs, the signed loopback hop, RO/RW, CSRF, malformed imports, preparation, and actor audit.
Browser checks cover the existing Demo and mocked Pilot/RO/unready interfaces.
These checks do not validate live Workbench credentials or an operational data source.

Remote acceptance must verify private ingress identity sanitization, actual peer CIDRs, Application-audience API keys, participant permissions, and browser CSRF behavior.
The first-live-program phase must reconcile actual records, approve freshness and acceptance protocols, and validate any predictive model.
Predefined guardrail cards and new MCP tools remain later milestones.

Official references: [Securing Applications](https://docs.cloudera.com/machine-learning/cloud/applications/topics/ml-securing-applications.html), [Cloudera AI API v2](https://docs.cloudera.com/machine-learning/cloud/api/topics/ml-api-v2.html).
