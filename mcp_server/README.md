# Vehicle NPI MCP server

## Query from an agent sandbox

Install with `python -m pip install --upgrade ./mcp_server` and configure the agent host
to launch `npi-mcp` over stdio. Set `NPI_API_BASE_URL` to the reachable application
URL ending in `/api`. The sandbox only needs this package and HTTP access;
it does not need the engineering data files or backend Python dependencies.
Localhost works only if the API and MCP process share a network namespace.
For a separate CAI Studio/agent workload, use the reachable Workbench Application
URL and its supported machine authentication mechanism. SSO redirects produce
an explicit error; an optional bearer header cannot bypass the Workbench ingress.

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

Install locally or use the following `uvx` source from the published `main` branch.
The package lives in `mcp_server`, so keep the `#subdirectory=mcp_server` suffix.

```json
{
  "mcpServers": {
    "vehicle-npi": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/FerdinandZhong/manufacturing_AI_review_design_blueprint.git@main#subdirectory=mcp_server", "npi-mcp"],
      "env": {
        "NPI_API_BASE_URL": "https://vehicle-npi-platform-h4ipg8.ml-c5697ef8-0c9.qzhong-a.a465-9q4k.cloudera.site/api"
      }
    }
  }
}
```

For Agent Studio fields, select stdio transport, use `uvx` as the command,
and supply the three `args` entries above as separate arguments. If the host
uses `uv run --with` instead, the same Git URL is the requirement and
`npi-mcp` is the executable. Use Python 3.11 or later.

Push changes to `origin/main` before restarting the MCP server. The dependency
tracks that branch, so no commit hash needs updating in Agent Studio. If uv
reuses a cached revision after a push, add `--refresh` before `--from` for the
next launch to force dependency revalidation.

An error such as `Updating ... (COMMIT)` followed by `Failed to resolve
--with requirement` means Git is trying to fetch the literal revision
`COMMIT`. Replace the entire dependency URL with the `@main` URL above; retrying
the unchanged configuration cannot fix that missing revision. A Git install
failure happens before MCP initialization or any application API request.

The configured application URL is this demo deployment; change it when using
another deployment. Omit `NPI_API_TOKEN` unless you have a supported application
token; never send the literal placeholder `OPTIONAL_APPLICATION_TOKEN`.

The client must be able to launch stdio processes and authenticate to the
private Workbench Application. `NPI_API_TOKEN` is only used when the deployed
application explicitly supports it; it is not a substitute for Workbench SSO
and is never the API v2 deployment key. Tool errors intentionally omit tokens
and upstream response bodies.
