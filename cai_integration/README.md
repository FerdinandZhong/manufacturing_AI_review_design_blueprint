# Deploy Vehicle NPI to Cloudera AI Workbench

The Application serves React and FastAPI in one workload. Workbench assigns `CDSW_APP_PORT`; the frontend listens there and proxies `/api` (including SSE) to `127.0.0.1:7078`. Source CSVs, SQLite, model files and the Lance dataset live in persistent project storage. Build artifacts are prepared by a Job before the Application starts. No GPU or live LLM is required.

## Automated deployment

Prerequisites: Python 3.11 Standard ML Runtime in the target workspace; API v2 key with project/job/application permissions; outbound package access during build; and the **current source** in a Git repository the workspace can clone, or already uploaded to an existing project. The current local checkout must be published/uploaded first: local uncommitted changes do not appear in a remote Git clone.

On your local machine or CI, install the small deployment-client dependencies:

```bash
python -m pip install httpx python-dotenv
cp cai_integration/.env.example .env
```

Edit `.env` with `CML_HOST`, `CML_API_KEY`, `RUNTIME_IDENTIFIER`, and either `GIT_URL` (new private project) or `CML_PROJECT_ID` (existing project). The scripts also accept Workbench-injected `CDSW_API_URL`, `CDSW_APIV2_KEY`, and `CDSW_PROJECT_ID`. Credentials are never printed or copied into the Application/Job payloads.

```bash
# Review the exact project, job and application settings without network access:
python cai_integration/bootstrap.py --dry-run

# Create the project, run preparation, and start the Application:
python cai_integration/bootstrap.py
```

The build Job executes `install → generate → prepare → smoke`. It installs Python dependencies, ensures Node >=22.12 via Node 22/nvm when needed, runs `npm ci` and the production build, initializes missing configuration, generates deterministic CSVs, prepares SQLite/ML/Lance, and verifies HIGH risk / five workers / CONDITIONAL in a temporary smoke DB. The Application is created only after the exact Job run succeeds. Failures and timeouts exit nonzero; a timeout does not cancel an existing remote workload.

IDs and the returned Application URL are written to `.cai/deployment.json` (gitignored). This file records partial progress if the build or launch fails. The API client uses the URL returned by Workbench; if the workspace omits it, open the named Application in its UI. `status: running` confirms platform state; `health_verified: false` explicitly means the authenticated app has not yet been browser-verified.

## Existing prepared project / application

```bash
python cai_integration/deploy_application.py --project-id PROJECT_ID --dry-run
python cai_integration/deploy_application.py --project-id PROJECT_ID
```

An exact matching Application is restarted. Configuration drift or duplicate matches stop deployment with an explanation; no Application is deleted. Update its Settings to the dry-run payload when intentionally changing resources/runtime. Unrelated names/subdomains are never modified.

For a source update, stop the Application first, update source in the project using the Workbench Git/files UI, then rerun `bootstrap.py --project-id PROJECT_ID`. Preparation rewrites generated CSVs, model and Lance artifacts, so bootstrap refuses to run while an Application in that project is active. Existing review records and model registrations remain in SQLite. These scripts do not run `git reset --hard`, delete data, or silently pull a different source revision.

## Workbench UI / AMP route

For a new project from this source, deploy `.project-metadata.yaml` through the AMP catalog. Alternatively, create one Python Job running `cai_integration/prepare_application.py` (2 CPU / 8 GB, 3600 seconds), wait for success, then create an Application:

- Name: Vehicle NPI Platform
- Script: `03_frontend/start_frontend.py`
- Runtime: Python 3.11 Standard
- Resources: 2 CPU / 8 GB; no GPU
- Subdomain: `vehicle-npi-platform` (or a unique DNS label)
- Environment: `BACKEND_PORT=7078`, `NPI_APP_MODE=prod`, optional `LLM_PROVIDER=caii`
- Keep unauthenticated access disabled. Do not set `CDSW_APP_PORT`; Workbench supplies it.

The launcher checks prepared files, rejects port collisions and exits if the backend cannot start. Application shutdown closes the proxy client and terminates its backend child. No installation, data generation, or Lance rebuild runs during Application startup.

## LLM and authentication

The application is private behind Workbench SSO. The in-app Models portal stores the active narration endpoint in project SQLite; alternatively configure `config/config.yaml`. `LLM_PROVIDER` overrides the configured provider. CAII endpoints can use `<workspace-domain>`, resolved from `CDSW_DOMAIN`; `/tmp/jwt` is used when no explicit inference key is configured. Model identifier/endpoint name must still be supplied. Unconfigured endpoints immediately fall back to deterministic narration.

The Models portal controls external narration, not the CPU design-risk model. All project members with app access should be trusted to use its existing write controls; this prototype does not add application-specific roles.

## MCP client

The separately packaged [`mcp_server`](../mcp_server/README.md) is a stdio
adapter for a compatible agent client. It calls the private Application API;
it is not another hosted service and never reads the project's SQLite or Lance
files. It provides read tools for program context, traditional-ML risk,
DVP&R results, traceability, knowledge metadata, saved reviews/evidence, and
one mutating `trigger_gate_review` tool. Gate approval and model configuration
remain in the cockpit.

The target client needs a verified route and authentication method to the
private Application. `CML_API_KEY` only controls API-v2 deployment automation;
it must never be used as `NPI_API_TOKEN` or included in MCP configuration.

## Acceptance and troubleshooting

Open the Application with a Workbench-authenticated browser:

1. Verify the cockpit loads and `/api/health` returns `{"status":"ok"}`.
2. Confirm thermal HIGH and MARGINAL; open a schematic, document, and photo in Knowledge base.
3. Open Models and verify the registry loads.
4. Run Gate Review: five workers complete, narrative appears, recommendation CONDITIONAL.
5. Restart the Application and confirm persisted model registrations/review data remain.

Read the preparation Job logs for install/build failures and Application logs for startup failures. A successful POST is not proof that an Application is healthy. If the workspace's API response schema differs, retain the API status and workload IDs for diagnosis; do not relax status checks to force success.

## Implementation reference

Adapted from the sibling AML `cai_integration` flow, with one ordered preparation Job instead of a multi-job chain. No long-running launch Job is necessary: the Application owns its own workload lifetime.

- [Cloudera Applications](https://docs.cloudera.com/machine-learning/cloud/applications/topics/ml-applications-c.html)
- [Cloudera API v2 reference](https://docs.cloudera.com/machine-learning/cloud/rest-api-reference/index.html)
