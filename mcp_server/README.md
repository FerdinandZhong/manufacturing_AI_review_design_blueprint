# Vehicle NPI MCP server

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
