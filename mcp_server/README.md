# Vehicle NPI MCP server

## Query from an agent sandbox

Install with `python -m pip install --upgrade ./mcp_server` and configure the agent host
to launch `npi-mcp` over stdio. Set `NPI_API_BASE_URL` to the reachable application
URL ending in `/api`. The sandbox only needs this package and HTTP access;
it does not need the engineering data files or backend Python dependencies.
Localhost works only if the API and MCP process share a network namespace.
For a separate CAI Studio/agent workload, use the reachable Workbench Application
URL and its supported machine authentication mechanism. Configure the required
application bearer token as `CDSW_APIV2_KEY`; the adapter sends it on every
application request as `Authorization: Bearer <token>`. The current deployment
redirects unauthenticated requests to Workbench SSO. A bearer token cannot bypass
an unsupported Workbench ingress path, so the Agent Studio runtime must have the
supported machine-access route as well as the token.

| Tool | Purpose |
| --- | --- |
| `list_programs` | Discover program IDs before querying. |
| `query_requirements` | Requirements, targets, units, priorities and source. |
| `query_design` | Design values, units, revisions and requirement links. |
| `query_bom` | Parts, quantities, cost/mass, supplier IDs and requirement links. |
| `query_test_results` | Saved results joined to their plans, standards and requirements. |
| `search_knowledge` | Find asset IDs by semantic caption search and optional ontology class. |
| `get_knowledge_asset` | Asset metadata, provenance and preview path. |
| `read_knowledge_content` | Actual document/SVG text or JPEG/PNG MCP image content. |

The four `query_*` tools accept `program_id`, optional `query` (literal text),
`requirement_id`, `limit` (1–100) and `offset`. Results include `items`, `total`
and `provenance`. Test queries also accept `verdict` (PASS/MARGINAL/FAIL).
For example, query `PACK-ATLAS-01` with `REQ-ATLAS-thermal`, inspect its design,
BOM and MARGINAL result, search for `thermal containment`, then read the returned
asset IDs. The current test results are persisted **synthetic bench outputs**;
no laboratory feed is configured. Querying them never runs the bench.

Swagger UI at `/api/docs` exposes **Engineering queries** and **Knowledge
queries** with parameter constraints, response schemas and Try it out:
`GET /api/programs/{pid}/data/{dataset}` and
`GET /api/asset/{asset_id}/content`. The latter returns up to 5 MiB of original
content, UTF-8 for text/SVG or base64 for binary files. The MCP adapter emits
raster images as native image blocks; actual image understanding depends on
the agent model. SVG is returned as source text. Binary PDFs remain available
through the API/preview; PDF parsing is not implemented by the adapter.

Existing context, risk, traceability, review and evidence tools remain available.
Read tools create no review or evidence rows. `trigger_gate_review` remains the
only mutating tool.

Verification: `python -m pytest mcp_server/tests/test_sandbox_queries.py -q`
launches a separate stdio MCP process against a temporary HTTP API and ops DB,
queries all four datasets and knowledge content, and checks no reviews were written.

`npi-mcp` is a stdio MCP adapter for the deployed Vehicle NPI Platform. It is a
thin HTTP client: all ML scores, DVP&R verdicts, traceability, and gate
recommendations are computed by the application. The only mutating tool is
`trigger_gate_review`, which creates a review and evidence record; it cannot
approve/reject a gate or change model configuration.

Install locally or use the following pinned `uvx` source with single-key authentication.
The package lives in `mcp_server`, so keep the `#subdirectory=mcp_server` suffix.

```json
{
  "mcpServers": {
    "vehicle-npi": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/FerdinandZhong/manufacturing_AI_review_design_blueprint.git@1d5bfa1468e1e8e7e60288e9e71f878c6ec31642#subdirectory=mcp_server", "npi-mcp"],
      "env": {
        "NPI_API_BASE_URL": "https://vehicle-npi-platform-h4ipg8.ml-c5697ef8-0c9.qzhong-a.a465-9q4k.cloudera.site/api",
        "CDSW_APIV2_KEY": "<workbench-api-key>"
      }
    }
  }
}
```

For Agent Studio fields, select stdio transport, use `uvx` as the command,
and supply the three `args` entries above as separate arguments. If the host
uses `uv run --with` instead, the same Git URL is the requirement and
`npi-mcp` is the executable. Use Python 3.11 or later.

Publish package changes before updating the pinned commit in Agent Studio.
Refresh tool discovery after changing the package revision.

An error such as `Updating ... (COMMIT)` followed by `Failed to resolve
--with requirement` means Git is trying to fetch the literal revision
`COMMIT`. Replace the entire dependency URL with the pinned URL above; retrying
the unchanged configuration cannot fix that missing revision. A Git install
failure happens before MCP initialization or any application API request.

The configured application URL is an example; change it for your deployment.
Set only `CDSW_APIV2_KEY` as the MCP credential. Raw keys and `Bearer <key>` both work.
Do not pass a literal placeholder or `${CDSW_APIV2_KEY}` as the value.
The adapter accepts `NPI_API_BEARER_TOKEN` and `NPI_API_TOKEN` only as legacy fallbacks.
An explicit `CDSW_APIV2_KEY` takes precedence over both aliases.

## Private Workbench authentication

Keep the Application private and use its HTTPS URL ending in `/api`.
The same Workbench key must pass Application ingress and authorize the API v2 project lookup.
For newly issued keys, select **Application** and **API** audiences.
The MCP process sends `Authorization: Bearer <key>`. It never supplies native identity headers.
The frontend validates that exact caller key through `POST /api/v2/auth/validate_key` with audience `API`.
It takes the authenticated username from that response.
It then checks `GET /api/v2/projects/{CDSW_PROJECT_ID}` on `CDSW_DOMAIN`.
It does not compare keys with a server environment variable or substitute the app owner's key.

The project response must identify the configured project and grant `read: true`.
Explicit `write: true` or `admin: true` grants RW; otherwise the caller remains RO.
Each request revalidates permissions. Redirects, invalid keys, missing permissions and platform failures fail closed.
The machine audit actor is the username verified by Workbench, not a client claim or the project owner.
Raw keys never enter audit records or tool errors.
The signed loopback hop and existing mutation checks remain enforced.
Browser requests retain native Workbench identity and same-origin mutation checks.

The client sends its key only to the configured application. The application sends it only to its configured Workbench origin.
A CAI Inference JWT or `/tmp/jwt` is not a Workbench API key.
A 401/403 or SSO redirect is an access failure, not an empty result.
The adapter's generic rejection message can represent ingress rejection or application permission denial.

Pilot mode exposes only validated read-only imports at this milestone.
Pilot review, synthetic risk, demo knowledge, and demo semantic tools remain unavailable.
Validate actual tool calls with participant permissions before a workshop. Discovery alone does not access the application.

Official references: [Application security](https://docs.cloudera.com/machine-learning/cloud/applications/topics/ml-securing-applications.html), [API keys and Application audience](https://docs.cloudera.com/machine-learning/cloud/api/topics/ml-api-v2.html).

MCP tests are an explicit development/release check: `python -m pytest mcp_server/tests -q`. Operational preparation installs the adapter but never runs its demo integration fixtures under Pilot mode. Run release tests only in an isolated local Demo test environment.
