# Cloudera AI Workbench application deployment plan

**Handoff status:** local CAI automation, persisted-review API changes, and the MCP adapter are implemented and locally verified. It has not been deployed to Workbench. Continue with a 5.6 model from the target-input and live-acceptance packages below; do not recreate the implementation from scratch.

## Objective and acceptance
Deploy the current Vehicle NPI prototype as one authenticated CAI Application: React static files on the Workbench-assigned application port, a co-located loopback FastAPI backend, persistent SQLite/model/Lance artifacts in project storage, and working SSE gate reviews. Preserve the deterministic HIGH / MARGINAL / CONDITIONAL demo.

Include a separately installable **stdio MCP adapter** for external agent clients to query the same data, ML results, and multimodal knowledge, and request a gate-review report. The existing five workers remain deterministic orchestration inside the backend. MCP introduces an external access surface; it does not replace their tools or allow an LLM to decide the gate outcome.

## Implementation sequence
1. Add `cai_integration` API v2 automation: find/create a private git-backed project, run a preparation Job and wait for that exact run to succeed, then create or restart the named Application and wait for its running state. Provide no-network dry-run and self-checks. Existing unrelated workloads must remain untouched.
2. Complete work packages F and G below: shared review execution/persistence, JSON service contracts, application access verification, and the thin MCP package. Validate them locally before integrating the deployment build.
3. Reuse the existing installer/generator/prepare scripts through one preparation entry point. Initialize missing configuration without overwriting existing settings, validate Node compatibility, and run a local application smoke check in the build Job.
4. Harden the production launcher: prioritize CDSW_APP_PORT, check prepared assets, reject port collision, fail on backend startup failure, preserve streaming, close HTTP resources and child processes on shutdown. Honor LLM_PROVIDER.
5. Align AMP metadata and document Git-backed automation, existing-project deployment, SSO, resource requirements, persistent storage, restart/update behavior, MCP client setup, and diagnostics.
6. Verify API payloads and failure paths with isolated tests, run backend regressions and frontend build/lint, and exercise production startup, assets, SSE, and actual MCP protocol calls on isolated local ports.
7. Deploy to the selected Workbench, record the project/build-run/application IDs and URL, and distinguish platform Running from verified application health and verified MCP access.

## Current discovery
The deployment reference is `../anti_money_laundry_blueprint/cai_integration`; the MCP reference is `/Users/zhongqishuai/Projects/cldr_projects/anti_money_laundry_blueprint/mcp_server`. Its destructive delete-all redeploy and public defaults will not be carried over. At the last inspection the checkout had no Git remote, no CML_HOST/API key/runtime environment settings, and no .env credentials. The user has supplied the Git source URL recorded in work package D. Workspace/project/runtime selection and source revision verification are still needed for step 7; implementation and local verification can proceed independently.

## Sources
- https://docs.cloudera.com/machine-learning/cloud/applications/topics/ml-applications-c.html
- https://docs.cloudera.com/machine-learning/cloud/rest-api-reference/index.html

## Existing implementation to preserve

Read `AGENTS.md` first. Preserve the previous cockpit, model portal, knowledge-base, and Chinese demo-story changes. The checkout is dirty, including unrelated `.omc`/`.claude` state; do not reset, clean, or broadly stage it. The user invoked `pua:pua` for this task; apply its execution and verification discipline within normal permissions.

| File | Draft responsibility |
|---|---|
| `cai_integration/client.py` | API authentication, pagination, status polling, result files |
| `cai_integration/setup_project.py` | Private Git-backed project creation or explicit project-ID selection |
| `cai_integration/bootstrap.py` | Project → preparation Job/run → Application orchestration |
| `cai_integration/deploy_application.py` | Private Application payload, scoped creation/restart, status and URL output |
| `cai_integration/prepare_application.py` | Installer → CSV generation → DB/ML/Lance preparation → smoke check |
| `cai_integration/smoke_test.py` | Offline API acceptance with temporary ops DB |
| `cai_integration/.env.example`, `README.md` | Configuration template and operational instructions |
| `01_installer/install.py` | Missing-config initialization and Node version handling |
| `03_frontend/start_frontend.py` | Port priority, artifact checks, streaming proxy, backend child lifecycle |
| `02_backend/common/config.py` | Example-config fallback and LLM_PROVIDER override |
| `.project-metadata.yaml`, `.gitignore` | Application environment settings and ignored deployment results |
| `02_backend/tests/test_workbench_deployment.py` | Deployment and launcher contract tests |

## Target topology and defaults

```text
Local/CI orchestration using Workbench API v2
  → create private project OR select explicit existing project
  → run one preparation Job and wait for its exact run ID
      install → generate → prepare → offline smoke
  → create/restart the named authenticated Application
  → verify platform status, then authenticated browser behavior

Application workload
  React/static server + API proxy on CDSW_APP_PORT
    → FastAPI child on 127.0.0.1:7078
      → persistent project CSV / SQLite / model / Lance storage

External agent client (for example, a compatible CAI Studio client)
  → launches npi-mcp locally over stdio
    → authenticated HTTP requests to the Application /api surface
      → the same FastAPI services, results, and review evidence
```

Defaults: Python 3.11 Standard Runtime; preparation Job 2 CPU / 8 GB with 3600-second timeout; Application 2 CPU / 8 GB, no GPU; subdomain `vehicle-npi-platform`; Workbench SSO enabled. A single preparation Job is sufficient for the prototype. The Application owns its workload lifetime; no permanent launch Job is needed.

The stdio server runs in the **MCP client's environment**, not as a second public CAI Application or permanent Job. A co-located client may use loopback for local verification; a client in a different workload cannot reach this Application through its own localhost. Remote Streamable HTTP MCP hosting is outside this implementation scope.

## Work package F — prepare the application API services

Execute after A and before G/B/C. Letters retain the previous handoff identifiers.

### Source findings and intended contracts

`02_backend/api/main.py` already exposes program/requirements/design/BOM/tests/results/risk/matrix, knowledge search, raw assets, and ontology. Its `GET /api/review/{pid}/stream` **executes and persists** a review. There is no JSON trigger or stored report retrieval endpoint. `agents/supervisor.py` uses `INSERT OR IGNORE` but reruns workers for a repeated review ID; that is not idempotency. Worker failures currently become prose, and the evidence table stores hashes/lineage rather than full result snapshots.

1. Extract a shared review service, proposed `02_backend/agents/review_service.py`, used by both the existing SSE route and new JSON routes. Preserve event types/order expected by the cockpit and keep the graph working. Existing SSE callers must use the same execution claim as JSON callers; do not create two independent runner paths. Keep the legacy GET trigger for frontend compatibility in this phase and document its side effect.
2. Add `POST /api/programs/{pid}/reviews`, accepting a required bounded `request_id`. Derive a stable review ID with uuid5 from program ID and request ID. Atomically claim execution in SQLite before starting workers. First request executes synchronously and returns the completed JSON report; a duplicate completed request returns its saved report, and a duplicate running request returns 202 with the same review ID and status URL. Never automatically repeat a timed-out POST with a new ID. Explicit new reviews require new request IDs.
3. Add `GET /api/reviews/{review_id}` returning execution status (`running`, `completed`, `failed`, `interrupted`), program/review IDs, structured worker results/errors, evidence references, recommendation, narrative, and separately the human decision/lifecycle state. Running results must identify partial data; failures must not look like successful reports. Unknown IDs return 404. A failed/interrupted ID remains terminal; a new request ID starts a deliberate retry.
4. Add an additive, versioned SQLite migration for execution claims, worker result snapshots, and final report data. Preserve existing reviews, annotations, and model registrations. Do not infer execution success from lifecycle state or a nonempty narrative. Treat old reviews without snapshots as legacy records with unavailable fields explicitly marked. Mark abandoned running executions interrupted on single-process app restart; this prototype does not introduce a durable job queue or multi-instance runner.
5. Persist snapshots of the structured inputs/results actually used by each worker, associated with evidence IDs and available source/model versions. Do not reconstruct an old report by querying changed current data, and do not claim the current fixed `src-v1` marker proves content identity. Add `GET /api/reviews/{review_id}/evidence` for bounded, paginated evidence plus snapshots. LLM prose is distinguishable from computed facts; missing worker evidence is a structured error. Preserve the existing pure recommendation formula; service failure/completeness status is separate from that recommendation.
6. Add `GET /api/asset/{asset_id}/metadata` with title, class, MIME type, description/caption, linked requirement/program, and preview path. Keep the current raw-byte route for images/documents. Bound search query length, `k` (1–20), evidence page size, and identifiers with explicit request validation; document schemas in OpenAPI. Exclude blobs and secrets from ordinary JSON responses. Do not label caption/hash retrieval as visual reasoning.
7. Define execution timeout and disconnect handling: bound worker/LLM calls; persist a terminal failure on execution timeout, and make completed results retrievable after client disconnect. A network timeout alone is not evidence the run failed. Serialize or reject incompatible concurrent work using SQLite claims without holding a write transaction across network/LLM calls. Ensure evidence writes and finalization survive worker exceptions without duplicate runs. Document and test the single Application process restriction.

### Application access and API proxy preparation

- Treat **Workbench API v2 credentials**, **application API access credentials**, and **LLM endpoint keys** as separate configurations. `CML_API_KEY` is for deployment control-plane calls; never assume it is an application bearer token.
- Verify the target Workbench's supported machine-access path to the private Application and the target MCP client's ability to supply it. An application bearer token cannot bypass Workbench SSO at the ingress. Keep SSO enabled; do not silently make the app public to enable MCP. Record the tested access method before remote acceptance.
- If application-level bearer authentication is needed by the supported access path, implement an explicit optional `NPI_API_TOKEN` server setting and validate it on the machine API surface. Scope access to query/report routes and review execution. Keep browser SSO sessions functional. Configure secrets through the target's supported secret/environment mechanism, never Git, examples, URLs, or logs. Do not add an unverified auth header bypass.
- Preserve Authorization and appropriate content types through the frontend proxy, without logging tokens. Validate JSON responses and reject login HTML/redirects with actionable, redacted errors. Use HTTPS remotely; allow HTTP only for explicit loopback development. Validate the configured base URL and encode path identifiers, preventing tool arguments from selecting another host.

Acceptance: isolated service tests verify old SSE behavior, JSON/SSE execution sharing, persisted reports/evidence, duplicate requests, worker failures, timeouts, restart interruption, and migration without data loss. All DB tests use temporary databases. Source CSV and Lance stay read-only at runtime. Atlas remains HIGH/MARGINAL/CONDITIONAL offline and with LLM narration enabled.

## Work package G — implement and package the MCP adapter

Reference inspected: AML `mcp_server/README.md`, `pyproject.toml`, `aml_mcp/server.py`, and `test_server.py`. Reuse the small FastMCP + httpx stdio pattern, not its customer domain. The reference's optional bearer header and redirect-following client do not establish private Workbench access compatibility.

Proposed package: `mcp_server/pyproject.toml`, `mcp_server/npi_mcp/__init__.py`, `mcp_server/npi_mcp/server.py`, `mcp_server/tests/test_server.py`, and `mcp_server/README.md`. Expose an `npi-mcp` console entry point; pin a tested compatible MCP SDK/httpx range and verify Python 3.11. Keep this dependency set separate from the Application runtime unless needed for a dedicated package check. Follow repository module/self-check conventions; self-checks must not start a blocking stdio server or touch the real DB.

| MCP tool | Application API contract | Effect |
|---|---|---|
| `list_programs` | Existing `GET /api/programs` | Read |
| `get_program_context` | Existing program detail plus requirements/design/BOM/tests routes; return named sections | Read |
| `get_design_risk` | Existing `GET /api/programs/{pid}/risk`; scores, bands, model explanation | Read |
| `get_test_results` | Existing `GET /api/programs/{pid}/results`; computed verdicts/margins | Read |
| `get_traceability` | Existing program detail coverage and `/matrix` | Read |
| `search_knowledge` | Existing `GET /api/kb/search`; bounded query/class/k | Read |
| `get_knowledge_asset` | Proposed asset metadata route; caption, links, MIME and preview path | Read |
| `get_gate_review` | Proposed `GET /api/reviews/{review_id}` | Read |
| `get_review_evidence` | Proposed paginated review evidence route | Read |
| `trigger_gate_review` | Proposed `POST /api/programs/{pid}/reviews`; stable request ID required | **Writes review/evidence only** |

1. Keep HTTP/domain logic in the API services. The adapter must not import backend modules, read project files/DB, recalculate ML scores, or parse SSE prose into decisions. Explicitly annotate tool effects. Do not expose approval/rejection, testbench execution, model configuration, credentials, retraining, or arbitrary URL/SQL tools.
2. Configure `NPI_API_BASE_URL` ending in `/api` and, only where the verified access method uses it, `NPI_API_TOKEN`. Validate inputs at both boundaries. Use bounded connection/read timeouts, disable automatic redirects, redact upstream errors, and return structured tool errors for auth, validation, missing objects, and unavailable services. Return the review ID on known in-progress outcomes; document lookup after ambiguous transport failure using the same request ID derivation. Never let the adapter silently start a new review to recover a timeout.
3. Return bounded metadata/text and preview references for knowledge assets. Binary rendering remains through the asset API and authenticated dashboard. Do not place large base64 images in every tool response or promise inline image display without client support verification. Label retrieved captions and source links so users can inspect the original material.
4. Document local editable installation and a revision-pinned uvx source: `git+https://github.com/FerdinandZhong/manufacturing_AI_review_design_blueprint.git@<verified-commit>#subdirectory=mcp_server`. Include a client configuration example with placeholders, startup diagnostics, authentication setup, and the only mutating tool clearly identified. Verify the chosen CAI client supports launching stdio; do not claim client compatibility from the AML README alone.
5. Add mocked HTTP mapping/error tests and a real stdio protocol smoke check (`initialize`, tool listing, read call, review call, report lookup) against an isolated local API. Protocol stdout must contain only MCP messages; logs use stderr. Check read tools cause no runtime writes, secrets are absent from tool output, unsupported mutations are absent, and duplicate trigger calls create one execution. Build/install the wheel in an isolated environment to verify the console entry point.

Acceptance: a compatible client can inspect Atlas thermal risk, MARGINAL test, coverage gap, and relevant historical asset metadata, then trigger one review and retrieve its CONDITIONAL report with evidence. Human approval stays in the cockpit. Local protocol acceptance and remote authenticated acceptance are recorded separately.

## Work package A — correct the API contract first

1. **Known bug:** the draft uses `/applications/{id}/restart`. The official API documents **`/applications/{id}:restart`**. Correct the code and its regression test; the existing test repeats the incorrect path.
2. Verify project/job/application request and response fields against official API v2 documentation and the target workspace version. Check runtime identifiers, resources, environment, creation status, pagination, and returned URL.
3. Review existing-application comparison. Full dictionary equality may reject API defaults or inherited environment fields. Compare intended settings using documented response shapes while detecting authentication/runtime/script drift.
4. Ensure restart success belongs to the requested restart, not a stale pre-restart Running response. Use the restart response and available workload IDs/timestamps; test supported transition behavior.
5. Keep authentication/list errors fatal. Duplicate names must not cause broad mutation. Do not propagate deployment credentials into Jobs/Applications or blindly retry creation POSTs.
6. Record non-secret resource IDs early enough to recover from a partial deployment.

Acceptance: mocked HTTP tests use documented routes and representative responses; build failure prevents launch; repeat deployment targets only the intended resources.

## Work package B — finish preparation and AMP support

1. Review installer changes for system Node, old system Node plus nvm, and nvm-only installations. All must select compatible Node/npm for `npm ci` and build. Confirm the current >=22.12 requirement against project dependencies.
2. Initialize missing configuration without overwriting existing settings. Verify LLM_PROVIDER override and offline fallback.
3. Validate preparation in a clean Linux Python 3.11 runtime: dependency installation, bundled photo, generated CSV, SQLite/ML/Lance, production frontend.
4. Validate AMP environment-variable syntax and resource settings against the AMP specification; keep its scripts aligned with automated deployment.
5. Smoke checks must use a temporary SQLite DB and prepared model/Lance artifacts, without contacting a configured LLM or changing the active project DB.
6. Run service migration/contract checks and build/install the MCP wheel in an isolated test environment. Package checks do not launch a permanent MCP process in the Application. Include the new API modules and MCP package in the verified Git revision used by the build.

Acceptance: preparation completes, Atlas invariants and assets pass, and existing review records/model registrations survive rebuilds.

## Work package C — verify Application lifecycle

1. Confirm the rewritten entry point executes under the selected Workbench runtime, including its Python/Jupyter execution semantics. The rewrite removed execution on ordinary module import; verify Application invocation remains supported.
2. Verify CDSW_APP_PORT precedence and the listener address against target Workbench behavior. Do not set the Workbench-assigned port in deployment payloads; keep the backend port distinct.
3. Missing artifacts, invalid ports, occupied backend ports, and early backend exit must fail clearly. Do not accept health responses from a different process on the same port.
4. Exercise JSON proxying, query strings, SVG/JPEG/document bytes, SSE, stream cancellation, and shutdown. Confirm HTTP resources close and backend children are reaped.
5. Verify later backend failure surfaces through health/API responses; determine whether workload termination is needed for Workbench recovery. Do not claim continuous monitoring unless implemented.
6. Preserve local start_app.py support and check development mode where affected.

Acceptance: isolated production startup/browser checks succeed and cleanup leaves no test-port listeners.

## Work package D — resolve real deployment inputs

At the last inspection there was no local Git remote, no `.env`, and none of the Workbench connection/runtime environment variables. The user subsequently supplied the deployment source repository:

`https://github.com/FerdinandZhong/manufacturing_AI_review_design_blueprint.git`

Use this as GIT_URL. Repository accessibility, branch, and whether it contains the current local changes are not yet verified. The Git URL does not supply the Workbench URL or project selection. Recheck for newly supplied workspace configuration without printing secrets.

| Required input | Configuration or source |
|---|---|
| Workspace URL | CML_HOST or Workbench-injected API URL |
| API v2 credential | Local gitignored `.env`: CML_API_KEY; never paste or print it |
| Project selection | Explicit CML_PROJECT_ID, or target/name for a new project |
| Runtime | Registered Python 3.11 Standard RUNTIME_IDENTIFIER; inspect catalog once authorized access exists |
| Current source | Accessible Git URL containing these changes, or current files already in the selected project |
| MCP client and application access | Target client's stdio support, network route, and verified private Application authentication method; distinct from API v2 credentials |
| Subdomain | Default unless unavailable or user chooses another |

A remote clone cannot include local uncommitted changes. Resolve source delivery before launching a build. Do not silently reuse sibling credentials, select another workspace, or upload the dirty checkout wholesale. Establish the exact destination and intended source files first.

If inputs remain missing, complete local implementation/verification and report precisely what is needed for live deployment. Do not invent an Application URL or mark deployment complete.

## Work package E — live deployment and acceptance

1. Review the dry-run payload for the selected target.
2. Create/select the project, verify current source availability, and run preparation.
3. Track the exact Job run to success; inspect logs on failure.
4. Create/restart the private Application and track the correct workload.
5. Open its authenticated URL: verify cockpit, Models, knowledge previews, thermal HIGH/MARGINAL, five workers, streamed narrative, CONDITIONAL.
6. Verify an Application restart preserves project data, using controlled test records.
7. Record project ID, build Job/run IDs, Application ID, source revision, runtime, URL, and actual verification status in `.cai/deployment.json` or a documented result file, with no credentials.
8. Install the revision-pinned MCP package in the target client environment and verify authenticated reads, knowledge metadata, one review trigger, and report/evidence lookup. Record `mcp_local_verified` and `mcp_remote_verified` separately, plus the tested client/version and non-secret access-method description. A missing machine-access path blocks remote MCP acceptance, not local implementation or browser acceptance.

Acceptance requires both platform Running and verified app behavior. If only platform status is checked, retain `health_verified: false`.

## Verification ledger

Confirmed during initial implementation:

- Deployment tests: **11 passed**. This predates contract review; the restart test mirrors the known route error and must be corrected.
- Bootstrap dry-run produced a private Application and one preparation Job payload without network access.
- `git diff --check` passed at that stage.
- Earlier frontend work passed 42 tests/browser checks, but those predate the launcher rewrite and do not validate current CAI changes.

Confirmed during this implementation pass:

- `python -m pytest 02_backend/tests mcp_server/tests -q`: **60 passed**.
- `python -m pytest 02_backend/tests/test_workbench_deployment.py -q`: **11 passed**.
- `python cai_integration/smoke_test.py`: HIGH thermal risk, assets, five workers, CONDITIONAL, and done event verified in a temporary ops DB.
- `python cai_integration/bootstrap.py --dry-run --project-id review-project --runtime-identifier review-python-3.11`: emitted private Job/Application payloads with no network access.
- `npm run build && npm run lint` in `03_frontend`: passed.
- MCP wheel built with `python -m build --no-isolation`; it installed in a temporary system-site-packages virtual environment. A real stdio `initialize`/`list_tools` exchange exposed 10 intended tools and no approval/model-configuration tool.
- An isolated browser-port startup could not be completed here: 7099 was already occupied and the sandbox denied bind on 7199. No process was stopped. Launcher contract tests passed, but Workbench/browser acceptance remains pending.

Started but final results were not collected before the skill-installation interruption:

- Backend suite followed by smoke check: execution session `44240`.
- Frontend `npm ci`, build, lint: execution session `80644`.

Collect these results if the sessions remain available. If unavailable or affected files have changed, rerun the relevant checks and record actual outcomes.

```bash
python -m pytest 02_backend/tests/test_workbench_deployment.py -q
python -m pytest 02_backend/tests -q
python cai_integration/smoke_test.py
python cai_integration/bootstrap.py --dry-run --project-id review-project --runtime-identifier review-python-3.11
```

Run `npm ci`, `npm run build`, and `npm run lint` from `03_frontend`. Use isolated test ports such as 7099/8199, preserving the user's app on 7078/8100 if running. Socket/browser checks may require sandbox escalation. Verify cleanup afterward. Run repository-required determinism/bootstrap checks where affected; reuse valid prior evidence for unrelated checks.

## Completion checklist

- [x] API contract reviewed, including the `:restart` correction and response normalization.
- [x] JSON/report/evidence contracts, additive migrations, and idempotency verified. SSE continues to use the same supervisor execution path.
- [x] MCP package build and actual stdio protocol checks passed locally.
- [ ] API proxy/auth behavior verified; deployment, application, and LLM credentials kept separate.
- [ ] Installer and AMP contracts verified.
- [ ] Production proxy, assets, SSE, failure handling, and shutdown verified.
- [x] Backend suite and frontend build/lint results captured for final code.
- [ ] Workspace/project/runtime/credentials and current source delivery resolved.
- [ ] Workbench preparation Job and Application deployment completed.
- [ ] Authenticated browser acceptance completed, IDs and URL recorded.
- [ ] Target MCP client and private Application access verified; remote tool workflow passed.
- [ ] Documentation updated to actual behavior and remaining limitations.

## Final plan review — 2026-09-10

This is a source-based plan review, not implementation or live-deployment validation. Work order is **A → F → G → B → C → D → E**, with discovery of D's inputs starting early. Runtime/client authentication discovery should precede any target-specific auth implementation in F. Local service/package work can continue while target inputs remain unavailable.

| Review finding | Resolution in this plan |
|---|---|
| MCP was absent from the previous deployment scope | Explicit adapter package, tool contracts, client installation, and local/remote acceptance added |
| AML server is stdio, not a hosted HTTP MCP service | Client owns the MCP process; CAI exposes the existing application API |
| Existing NPI GET/SSE runs a review and repeated IDs rerun workers | Shared execution claim, stable JSON request identity, persisted status/report, and compatible SSE path required |
| Existing evidence hashes cannot reproduce historical worker results | Add snapshots tied to evidence IDs; mark legacy records honestly |
| SSO and bearer headers were easy to conflate | Separate credential roles and require a verified private Application machine-access path |
| A synchronous trigger can outlive a client request | Bounded execution, stable ID, status retrieval, terminal failure/interruption semantics; no blind new-run retry |
| New persistence could damage existing demo data | Additive migration, temporary DB tests, and explicit rebuild/restart persistence acceptance |
| MCP tools could bypass human review or duplicate domain logic | Query tools plus one review-only mutation; approval/configuration remain outside MCP |
| Platform Running and mocked HTTP tests are insufficient | Browser, real stdio, and authenticated remote MCP checks have distinct recorded outcomes |
| Known deployment route bug and incomplete test evidence remain | A retains the `:restart` correction; the verification ledger remains explicitly historical |

Implementation touchpoints: `02_backend/api/main.py`, `agents/supervisor.py`, proposed `agents/review_service.py`, `common/evidence.py`, `data_generation/schema.py` plus a migration helper, `knowledge/kb.py` for metadata access if needed, `03_frontend/start_frontend.py`, new `mcp_server/`, backend/package tests, deployment preparation, and operational/API documentation. Frontend changes are needed only if service compatibility requires them; preserve the visible cockpit workflow.

Remaining external dependencies are workspace/project/runtime configuration, source revision delivery, and target-client/private-Application access verification. No live deployment or MCP compatibility is asserted. The plan is ready for implementation handoff; these dependencies remain explicit acceptance gates.

## Suggested 5.6 continuation prompt

> Continue CAI integration from `docs/workbench-deployment-plan.md`. Preserve the draft implementation and unrelated changes. Follow A → F → G → B → C → D → E, discovering target inputs early: correct `:restart`, implement shared review/API persistence and the AML-style stdio MCP adapter, verify migration/idempotency/auth boundaries and local protocol behavior, then finish preparation and Application lifecycle checks. Deploy the verified source revision once workspace/project/runtime/credentials are available. Validate the authenticated cockpit and MCP client separately. Preserve deterministic HIGH/MARGINAL/CONDITIONAL and human-only approval. Report observed results; do not assume earlier checks passed or that a deployment API key authenticates the Application.
