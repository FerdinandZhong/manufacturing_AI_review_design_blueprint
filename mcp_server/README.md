# Vehicle NPI MCP server

## Query from an agent sandbox

Install with `python -m pip install ./mcp_server` and configure the agent host
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

Install locally or with a revision-pinned `uvx` source after the repository
revision is published:

```json
{
  "mcpServers": {
    "vehicle-npi": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/FerdinandZhong/manufacturing_AI_review_design_blueprint.git@COMMIT#subdirectory=mcp_server", "npi-mcp"],
      "env": {
        "NPI_API_BASE_URL": "https://vehicle-npi-platform.<workspace-domain>/api",
        "NPI_API_TOKEN": "OPTIONAL_APPLICATION_TOKEN"
      }
    }
  }
}
```

The client must be able to launch stdio processes and authenticate to the
private Workbench Application. `NPI_API_TOKEN` is only used when the deployed
application explicitly supports it; it is not a substitute for Workbench SSO
and is never the API v2 deployment key. Tool errors intentionally omit tokens
and upstream response bodies.
