"""Stdio MCP adapter for a deployed Vehicle NPI Platform.

This package is deliberately a thin HTTP client. It neither imports the NPI
backend nor reads SQLite/Lance files, so every score, verdict and gate
recommendation still comes from the deployed deterministic application.
"""
import os
from typing import Literal
from mcp.types import ImageContent, TextContent, ToolAnnotations
from urllib.parse import quote, urlsplit

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("vehicle-npi")
_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)


def _base_url() -> str:
    value = os.environ.get("NPI_API_BASE_URL", "").rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError("NPI_API_BASE_URL must be an HTTP(S) API URL, for example https://npi.<domain>/api")
    if not parsed.path.rstrip("/").endswith("/api"):
        raise RuntimeError("NPI_API_BASE_URL must end with /api")
    return value


def _headers() -> dict[str, str]:
    token = os.environ.get("NPI_API_TOKEN", "").strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


def _request(method: str, path: str, *, params: dict | None = None, payload: dict | None = None) -> dict | list:
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=False) as client:
            response = client.request(method, _base_url() + path,
                                      params={k: v for k, v in (params or {}).items() if v is not None},
                                      json=payload, headers=_headers())
    except httpx.HTTPError as exc:
        raise RuntimeError("NPI API is unavailable") from None
    if 300 <= response.status_code < 400:
        raise RuntimeError("NPI API redirected the request; configure the authenticated Application URL")
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"NPI API returned HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("NPI API returned a non-JSON response") from exc


def _program_path(program_id: str, suffix: str = "") -> str:
    if not program_id or len(program_id) > 128:
        raise ValueError("program_id is required and must be at most 128 characters")
    return "/programs/" + quote(program_id, safe="-_~") + suffix


@mcp.tool()
def list_programs() -> list:
    """List NPI programs. Read-only."""
    return _request("GET", "/programs")


@mcp.tool()
def get_program_context(program_id: str) -> dict:
    """Return the program, requirements, design, BOM and test plan context. Read-only."""
    root = _program_path(program_id)
    return {"program": _request("GET", root), "requirements": _request("GET", root + "/requirements"),
            "design": _request("GET", root + "/design"), "bom": _request("GET", root + "/bom"),
            "tests": _request("GET", root + "/tests")}


@mcp.tool()
def get_design_risk(program_id: str) -> dict:
    """Return traditional-ML design risk scores and explanation. Read-only."""
    return _request("GET", _program_path(program_id, "/risk"))


@mcp.tool()
def get_test_results(program_id: str) -> list:
    """Return deterministic DVP&R test verdicts and margins. Read-only."""
    return _request("GET", _program_path(program_id, "/results"))


@mcp.tool()
def get_traceability(program_id: str) -> dict:
    """Return requirement/design/test traceability matrix. Read-only."""
    return _request("GET", _program_path(program_id, "/matrix"))


@mcp.tool()
def search_knowledge(query: str, ontology_class: str | None = None, limit: int = 3) -> list:
    """Search multimodal knowledge metadata. Captions and source links are returned, not image blobs. Read-only."""
    if not query or len(query) > 500 or not 1 <= limit <= 20:
        raise ValueError("query must be 1-500 characters and limit must be 1-20")
    return _request("GET", "/kb/search", params={"q": query, "cls": ontology_class, "k": limit})


@mcp.tool()
def get_knowledge_asset(asset_id: str) -> dict:
    """Return knowledge asset metadata and authenticated preview path. Read-only."""
    if not asset_id or len(asset_id) > 128:
        raise ValueError("asset_id is required and must be at most 128 characters")
    return _request("GET", "/asset/" + quote(asset_id, safe="-_~") + "/metadata")


@mcp.tool()
def get_gate_review(review_id: str) -> dict:
    """Return persisted review status, worker outputs, recommendation and narrative. Read-only."""
    return _request("GET", "/reviews/" + quote(review_id, safe="-_~"))


@mcp.tool()
def get_review_evidence(review_id: str, limit: int = 20, offset: int = 0) -> dict:
    """Return bounded evidence snapshots for a persisted review. Read-only."""
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("limit must be 1-100 and offset must be non-negative")
    return _request("GET", "/reviews/" + quote(review_id, safe="-_~") + "/evidence", params={"limit": limit, "offset": offset})


@mcp.tool()
def trigger_gate_review(program_id: str, request_id: str) -> dict:
    """Run one gate review and persist its report/evidence. This is the only mutating tool; it cannot approve a gate."""
    if not request_id or len(request_id) > 128:
        raise ValueError("request_id is required and must be at most 128 characters")
    return _request("POST", _program_path(program_id, "/reviews"), payload={"request_id": request_id})


def _query_data(program_id, dataset, query, requirement_id, limit, offset, verdict=None):
    if len(query) > 200 or not 1 <= limit <= 100 or offset < 0:
        raise ValueError("query must be at most 200 characters; limit 1-100; offset non-negative")
    return _request("GET", _program_path(program_id, "/data/" + dataset),
                    params={"q": query, "requirement_id": requirement_id, "limit": limit,
                            "offset": offset, "verdict": verdict})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def query_requirements(program_id: str, query: str = "", requirement_id: str | None = None,
             limit: int = 20, offset: int = 0) -> dict:
    """Query design requirements. Supports literal text search, requirement links and pagination."""
    return _query_data(program_id, "requirements", query, requirement_id, limit, offset)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def query_design(program_id: str, query: str = "", requirement_id: str | None = None,
             limit: int = 20, offset: int = 0) -> dict:
    """Query design specifications. Supports literal text search, requirement links and pagination."""
    return _query_data(program_id, "design", query, requirement_id, limit, offset)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def query_bom(program_id: str, query: str = "", requirement_id: str | None = None,
             limit: int = 20, offset: int = 0) -> dict:
    """Query BOM parts, supplier IDs, costs and masses. Supports literal text search, requirement links and pagination."""
    return _query_data(program_id, "bom", query, requirement_id, limit, offset)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def query_test_results(program_id: str, query: str = "", requirement_id: str | None = None,
             limit: int = 20, offset: int = 0, verdict: Literal["PASS", "MARGINAL", "FAIL"] | None = None) -> dict:
    """Query saved test results with test plans; demo records are synthetic, not laboratory measurements. Supports literal text search, requirement links and pagination."""
    return _query_data(program_id, "test_results", query, requirement_id, limit, offset, verdict)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def read_knowledge_content(asset_id: str) -> list[TextContent | ImageContent]:
    """Read actual knowledge content in the agent sandbox. Documents/SVG return text;
    JPEG/PNG return MCP images. Search first for asset IDs and provenance.
    Rendering images depends on the host/model supporting image content.
    """
    if not asset_id or len(asset_id) > 128:
        raise ValueError("asset_id must be 1-128 characters")
    data = _request("GET", "/asset/" + quote(asset_id, safe="-_~") + "/content")
    context = TextContent(type="text", text=f"{asset_id}: {data['provenance']}")
    if data["mime_type"] in {"image/jpeg", "image/png"}:
        return [context, ImageContent(type="image", mimeType=data["mime_type"], data=data["content"])]
    if data["encoding"] == "utf-8":
        return [context, TextContent(type="text", text=data["content"])]
    return [context, TextContent(type="text", text="Binary document; inspect via the authenticated asset preview.")]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    old = os.environ.get("NPI_API_BASE_URL")
    os.environ["NPI_API_BASE_URL"] = "https://npi.example.com/api"
    assert _base_url() == "https://npi.example.com/api"
    if old is None:
        del os.environ["NPI_API_BASE_URL"]
    else:
        os.environ["NPI_API_BASE_URL"] = old
    print("npi-mcp self-check OK")
