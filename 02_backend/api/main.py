"""Vehicle NPI Platform FastAPI backend — HTTP surface over already-approved
backend modules (source, traceability, ml, kb, ontology, agents). Mirrors
AML's api/main.py structure.

Code decides, LLM narrates: this layer introduces no new LLM calls and does
not change how run_gate_review's recommendation is computed — it's plumbing.

Two-store rule: endpoints read via source/traceability/ml/kb/ontology
(source+derived reads) and common.db (ops reads). The only writes here are
POST .../testbench (delegates to run_test_bench) and
POST /api/review/{review_id}/decision (writes annotations + gate_reviews).
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "02_backend"))

import json
import math
import sqlite3
from urllib.parse import urlsplit
from agents import llm_client
import uuid
from typing import Literal

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field

from common.db import get_connection
from common import source
from engineering import traceability
from engineering.test_bench import run_test_bench
from ml import risk_model
from knowledge import kb, ontology
from agents.supervisor import run_gate_review
from agents.tools import TOOLS
from common.evidence import list_review_evidence

app = FastAPI(
    title="Vehicle NPI Platform",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def _clean(obj):
    """Source CSVs go through pandas, which represents blank cells as NaN —
    not valid JSON. Recursively swap float NaN for None before responding."""
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj


def _get_program_or_404(program_id: str) -> dict:
    prog = source.get_program(program_id)
    if prog is None:
        raise HTTPException(404, f"Program not found: {program_id}")
    return prog


def _review_report(row: sqlite3.Row | dict) -> dict:
    """Render persisted review state without recomputing any source data."""
    item = dict(row)
    for field in ("worker_results",):
        raw = item.get(field)
        if raw:
            try:
                item[field] = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                item[field] = None
    item["legacy_snapshot_unavailable"] = item.get("worker_results") is None
    return item


def _review_id(program_id: str, request_id: str) -> str:
    return "REV-" + uuid.uuid5(uuid.NAMESPACE_URL, f"npi-review:{program_id}:{request_id}").hex[:20].upper()


_MODALITY_MEDIA_TYPE = {"image": "image/png", "pdf": "application/pdf", "text": "text/plain"}
_DECISIONS = {"APPROVED", "APPROVED_WITH_CONDITIONS", "REJECTED"}


# ── programs ────────────────────────────────────────────────────────────────

class QueryPage(BaseModel):
    program_id: str
    dataset: str
    total: int
    limit: int
    offset: int
    items: list[dict]
    provenance: str


@app.get('/api/programs/{pid}/data/{dataset}', response_model=QueryPage,
         tags=['Engineering queries'], summary='Query requirements, designs, BOM, plans or stored test results')
def query_program_data(pid: str, dataset: Literal['requirements', 'design', 'bom', 'test_plans', 'test_results'],
                       q: str = Query(default='', max_length=200),
                       requirement_id: str | None = Query(default=None, max_length=128),
                       verdict: Literal['PASS', 'MARGINAL', 'FAIL'] | None = None,
                       limit: int = Query(default=20, ge=1, le=100),
                       offset: int = Query(default=0, ge=0)):
    """Read stored engineering records with links to their requirement and test plan.

    q is a case-insensitive literal text match. requirement_id follows BOM →
    design → requirement links. verdict applies only to test_results.
    Tests are persisted synthetic bench computations in this demo, not physical
    laboratory measurements. This endpoint never runs the bench or scores ML.
    """
    _get_program_or_404(pid)
    if verdict and dataset != 'test_results':
        raise HTTPException(422, 'verdict is only supported for test_results')
    loaders = {'requirements': source.list_requirements, 'design': source.list_design_specs,
               'bom': source.list_bom, 'test_plans': source.list_test_plans,
               'test_results': lambda p: TOOLS['get_test_results'](None, p)}
    rows = _clean(loaders[dataset](pid))
    if dataset == 'bom':
        specs = {s['spec_id']: s for s in source.list_design_specs(pid)}
        rows = [{**r, 'req_id': specs.get(r['spec_id'], {}).get('req_id')} for r in rows]
    if dataset == 'test_results':
        plans = {p['test_id']: p for p in source.list_test_plans(pid)}
        rows = [{**r, 'test_plan': plans.get(r['test_id']),
                 'req_id': plans.get(r['test_id'], {}).get('req_id')} for r in rows]
    rows = [r for r in rows if (not requirement_id or r.get('req_id') == requirement_id)
            and (not verdict or r.get('verdict') == verdict)
            and (not q or q.casefold() in json.dumps(r, ensure_ascii=False).casefold())]
    rows.sort(key=lambda r: json.dumps(r, sort_keys=True))
    return QueryPage(program_id=pid, dataset=dataset, total=len(rows), limit=limit, offset=offset,
                     items=rows[offset:offset + limit], provenance=(
                         'Persisted synthetic test-bench results; not physical lab measurements'
                         if dataset == 'test_results' else 'Seeded engineering reference data'))


class AssetContent(BaseModel):
    asset_id: str
    mime_type: str
    encoding: Literal['utf-8', 'base64']
    content: str
    provenance: str


@app.get('/api/asset/{asset_id}/content', response_model=AssetContent,
         tags=['Knowledge queries'], summary='Read the original document or image content')
def read_asset_content(asset_id: str):
    """Fetch bounded asset content for agents that cannot open browser preview links.

    Text and SVG are UTF-8; raster images and PDF files are base64 encoded.
    Images retain their source provenance. Content larger than 5 MiB is rejected.
    """
    import base64
    try:
        asset = kb.get_asset(asset_id)
    except KeyError:
        raise HTTPException(404, 'Asset not found')
    blob = bytes(asset['blob'])
    if len(blob) > 5 * 1024 * 1024:
        raise HTTPException(413, 'Asset exceeds the 5 MiB agent content limit')
    mime = get_asset(asset_id).media_type
    is_text = mime.startswith('text/') or mime == 'image/svg+xml'
    return AssetContent(asset_id=asset_id, mime_type=mime,
                        encoding='utf-8' if is_text else 'base64',
                        content=blob.decode('utf-8') if is_text else base64.b64encode(blob).decode('ascii'),
                        provenance=asset.get('provenance', ''))

@app.get("/api/programs")
def list_programs():
    return _clean(source.list_programs())


@app.get("/api/programs/{pid}")
def get_program(pid: str):
    program = _get_program_or_404(pid)
    return _clean({
        "program": program,
        "coverage": traceability.coverage(pid),
        "matrix": traceability.build_matrix(pid),
    })


@app.get("/api/programs/{pid}/requirements")
def get_requirements(pid: str):
    _get_program_or_404(pid)
    return _clean(source.list_requirements(pid))


@app.get("/api/programs/{pid}/design")
def get_design(pid: str):
    _get_program_or_404(pid)
    return _clean(source.list_design_specs(pid))


@app.get("/api/programs/{pid}/bom")
def get_bom(pid: str):
    _get_program_or_404(pid)
    return _clean(source.list_bom(pid))


@app.get("/api/programs/{pid}/tests")
def get_tests(pid: str):
    _get_program_or_404(pid)
    return _clean(source.list_test_plans(pid))


@app.get("/api/programs/{pid}/results")
def get_results(pid: str):
    _get_program_or_404(pid)
    return TOOLS["get_test_results"](None, pid)


@app.get("/api/programs/{pid}/risk")
def get_risk(pid: str):
    _get_program_or_404(pid)
    return {"scores": risk_model.get_scores(pid), "explanation": risk_model.explain()}


@app.get("/api/programs/{pid}/matrix")
def get_matrix(pid: str):
    _get_program_or_404(pid)
    return _clean(traceability.build_matrix(pid))


@app.post("/api/programs/{pid}/testbench")
def post_testbench(pid: str):
    _get_program_or_404(pid)
    return run_test_bench(pid)


# ── knowledge base / ontology ───────────────────────────────────────────────

@app.get("/api/kb/search")
def kb_search(q: str = Query(min_length=1, max_length=500), cls: str | None = None,
              k: int = Query(default=3, ge=1, le=20)):
    # kb.search() rows carry the raw asset blob; drop it here (fetch it via
    # /api/asset/{id} instead) so search results stay small JSON, not binary.
    hits = kb.search(q, ontology_filter=cls, k=k)
    return [{kk: v for kk, v in h.items() if kk != "blob"} for h in hits]


@app.get("/api/asset/{asset_id}")
def get_asset(asset_id: str):
    try:
        asset = kb.get_asset(asset_id)
    except KeyError:
        raise HTTPException(404, f"Asset not found: {asset_id}")
    media_type = _MODALITY_MEDIA_TYPE.get(asset["modality"], "application/octet-stream")
    blob = bytes(asset["blob"])
    if blob.startswith(b"<svg"):
        media_type = "image/svg+xml"
    elif blob.startswith(b"\xff\xd8"):
        media_type = "image/jpeg"
    elif asset["modality"] == "pdf" and not blob.startswith(b"%PDF"):
        media_type = "text/plain"
    return Response(content=blob, media_type=media_type, headers={"X-Content-Type-Options": "nosniff"})


@app.get("/api/asset/{asset_id}/metadata")
def get_asset_metadata(asset_id: str):
    try:
        asset = kb.get_asset(asset_id)
    except KeyError:
        raise HTTPException(404, f"Asset not found: {asset_id}")
    return {key: asset.get(key) for key in (
        "asset_id", "ontology_class", "modality", "title", "caption_text",
        "program_ref", "linked_entity_type", "linked_entity_id", "provenance",
        "source_url", "license_url"
    )} | {"preview_path": f"/api/asset/{asset_id}"}


@app.get("/api/ontology")
def get_ontology():
    return {"classes": ontology.classes(), "relations": ontology.relations()}


# ── gate review (agents) ────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


@app.post("/api/programs/{pid}/reviews")
def create_review(pid: str, body: ReviewRequest, conn=Depends(get_db)):
    """Run one deterministic review for a caller supplied idempotency key.

    The first request is synchronous for the demo. A concurrent caller sees the
    same review ID and can poll its stored report instead of starting workers a
    second time.
    """
    _get_program_or_404(pid)
    review_id = _review_id(pid, body.request_id)
    try:
        conn.execute(
            "INSERT INTO gate_reviews(review_id, program_id, request_id, state, execution_status) "
            "VALUES (?, ?, ?, 'GATE_REVIEW', 'running')",
            (review_id, pid, body.request_id),
        )
        conn.commit()
        claimed = True
    except sqlite3.IntegrityError:
        conn.rollback()
        claimed = False

    if not claimed:
        row = conn.execute("SELECT * FROM gate_reviews WHERE program_id=? AND request_id=?", (pid, body.request_id)).fetchone()
        if row is None:
            raise HTTPException(409, "Unable to resolve existing review request")
        report = _review_report(row)
        if report.get("execution_status") == "running":
            return Response(
                content=json.dumps({"review_id": review_id, "execution_status": "running", "status_url": f"/api/reviews/{review_id}"}),
                media_type="application/json", status_code=status.HTTP_202_ACCEPTED,
            )
        return report

    try:
        # Exhaust the shared SSE generator: this is deliberately the same
        # orchestration path the browser uses, not a second review engine.
        list(run_gate_review(review_id, pid))
    except Exception as exc:
        conn.execute("UPDATE gate_reviews SET execution_status='failed', execution_error=?, completed_at=datetime('now') WHERE review_id=?",
                     (type(exc).__name__, review_id))
        conn.commit()
        raise HTTPException(500, "Gate review execution failed") from None
    row = conn.execute("SELECT * FROM gate_reviews WHERE review_id=?", (review_id,)).fetchone()
    return _review_report(row)


@app.get("/api/reviews/{review_id}")
def get_review(review_id: str, conn=Depends(get_db)):
    row = conn.execute("SELECT * FROM gate_reviews WHERE review_id=?", (review_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Gate review not found: {review_id}")
    return _review_report(row)


@app.get("/api/reviews/{review_id}/evidence")
def get_review_evidence(review_id: str, limit: int = Query(default=20, ge=1, le=100),
                        offset: int = Query(default=0, ge=0), conn=Depends(get_db)):
    exists = conn.execute("SELECT 1 FROM gate_reviews WHERE review_id=?", (review_id,)).fetchone()
    if exists is None:
        raise HTTPException(404, f"Gate review not found: {review_id}")
    rows = list_review_evidence(review_id, limit=limit, offset=offset)
    return {"review_id": review_id, "limit": limit, "offset": offset, "evidence": rows}

@app.get("/api/review/{pid}/stream")
def review_stream(pid: str, review_id: str):
    _get_program_or_404(pid)

    def event_stream():
        for evt in run_gate_review(review_id, pid):
            yield f"data: {json.dumps(evt)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


class DecisionBody(BaseModel):
    decision: str
    rationale: str = ""
    adjudicator: str = ""


@app.post("/api/review/{review_id}/decision")
def review_decision(review_id: str, body: DecisionBody, conn=Depends(get_db)):
    if body.decision not in _DECISIONS:
        raise HTTPException(400, f"decision must be one of {sorted(_DECISIONS)}")

    exists = conn.execute("SELECT 1 FROM gate_reviews WHERE review_id=?", (review_id,)).fetchone()
    if exists is None:
        raise HTTPException(404, f"Gate review not found: {review_id}")

    annotation_id = f"ANN-{uuid.uuid4().hex[:12].upper()}"
    conn.execute(
        "INSERT INTO annotations(annotation_id,review_id,decision,rationale,adjudicator) VALUES(?,?,?,?,?)",
        (annotation_id, review_id, body.decision, body.rationale, body.adjudicator),
    )
    conn.execute(
        "UPDATE gate_reviews SET decided_by=?, decision=?, state='RELEASED' WHERE review_id=?",
        (body.adjudicator, body.decision, review_id),
    )
    conn.commit()

    row = conn.execute("SELECT * FROM gate_reviews WHERE review_id=?", (review_id,)).fetchone()
    return dict(row)


def _validate_model(provider, api_base):
    if provider not in {"openai", "openai_compatible", "caii", "vllm", "ollama"}:
        raise HTTPException(400, "Unsupported model provider")
    if not api_base and provider != "openai":
        raise HTTPException(400, "API base is required for this provider")
    if api_base:
        try:
            url = urlsplit(api_base)
            _ = url.port  # rejects invalid port syntax
        except ValueError:
            raise HTTPException(400, "Invalid API base URL")
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise HTTPException(400, "API base must be an HTTP(S) URL without credentials, query, or fragment")


class RegisterModelBody(BaseModel):
    alias: str
    provider: str                       # openai | openai_compatible | caii | vllm | ollama
    model_identifier: str
    api_base: str | None = None
    api_key: str | None = None


def _mask_key(k: str | None) -> str:
    if not k:
        return ""
    return ("••••" + k[-4:]) if len(k) > 4 else "••••"


@app.get("/api/config/llm/models")
def list_llm_models(conn=Depends(get_db)):
    rows = conn.execute(
        "SELECT id, alias, provider, model_identifier, api_base, api_key, is_active "
        "FROM llm_models ORDER BY created_at DESC"
    ).fetchall()
    return {"models": [{**dict(r), "api_key": _mask_key(r["api_key"])} for r in rows]}


@app.post("/api/config/llm/models")
def register_llm_model(body: RegisterModelBody, conn=Depends(get_db)):
    """Register a model and make it active. Agents resolve the active row on each call."""
    if not body.alias.strip() or not body.model_identifier.strip():
        raise HTTPException(400, "alias and model_identifier are required")
    _validate_model(body.provider, body.api_base)
    try:
        conn.execute("UPDATE llm_models SET is_active=0")
        conn.execute(
            "INSERT INTO llm_models (alias, provider, model_identifier, api_base, api_key, is_active) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (body.alias.strip(), body.provider, body.model_identifier.strip(),
             body.api_base, body.api_key),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(400, f"Alias '{body.alias}' already exists")
    return {"ok": True, "alias": body.alias, "model": body.model_identifier, "active": True}


class UpdateModelBody(BaseModel):
    alias: str | None = None
    provider: str | None = None
    model_identifier: str | None = None
    api_base: str | None = None
    api_key: str | None = None   # blank/omitted = keep existing (list masks it)


@app.put("/api/config/llm/models/{model_id}")
def update_llm_model(model_id: int, body: UpdateModelBody, conn=Depends(get_db)):
    """Edit a registered model (e.g. fix a typo'd api_base). api_key is kept when
    left blank, since the list only ever returns a masked key."""
    row = conn.execute("SELECT * FROM llm_models WHERE id=?", (model_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Model not found")
    cur = dict(row)
    alias = (body.alias or cur["alias"]).strip()
    provider = body.provider or cur["provider"]
    model_identifier = (body.model_identifier or cur["model_identifier"]).strip()
    # form always sends api_base; empty string clears it to NULL (OpenAI default)
    api_base = ((body.api_base if body.api_base is not None else cur["api_base"]) or "").strip() or None
    _validate_model(provider, api_base)
    if not alias or not model_identifier:
        raise HTTPException(400, "Alias and model identifier are required")
    api_key = body.api_key.strip() if (body.api_key and body.api_key.strip()) else cur["api_key"]
    try:
        conn.execute(
            "UPDATE llm_models SET alias=?, provider=?, model_identifier=?, api_base=?, api_key=? WHERE id=?",
            (alias, provider, model_identifier, api_base, api_key, model_id),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(400, f"Alias '{alias}' already exists")
    return {"ok": True, "id": model_id, "alias": alias}


@app.post("/api/config/llm/models/{model_id}/activate")
def activate_llm_model(model_id: int, conn=Depends(get_db)):
    row = conn.execute("SELECT alias, model_identifier FROM llm_models WHERE id=?", (model_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Model not found")
    conn.execute("UPDATE llm_models SET is_active=0")
    conn.execute("UPDATE llm_models SET is_active=1 WHERE id=?", (model_id,))
    conn.commit()
    return {"ok": True, "alias": row["alias"], "model": row["model_identifier"], "active": True}


@app.post("/api/config/llm/models/{model_id}/test")
def test_llm_model(model_id: int, conn=Depends(get_db)):
    """Probe a registered model's endpoint without changing which model is active."""
    row = conn.execute(
        "SELECT provider, model_identifier, api_base, api_key FROM llm_models WHERE id=?", (model_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Model not found")
    ok, message = llm_client.probe(row["api_base"], row["model_identifier"], row["api_key"])
    return {"ok": ok, "message": message if ok else "Connection test failed. Check the endpoint, model identifier, and credentials."}



if __name__ == "__main__":
    from fastapi.testclient import TestClient
    from common.db import init_db
    from ml.train import train

    import tempfile
    import common.db as db
    _tmp = tempfile.mkdtemp()
    db.get_db_path = lambda: os.path.join(_tmp, "self_check.db")
    init_db()
    showcase = "PACK-ATLAS-01"
    for _p in ["PACK-ORION-00", "PACK-VEGA-00", showcase]:
        run_test_bench(_p)
    train()
    risk_model.score_program(showcase)
    kb.build_kb()

    client = TestClient(app)

    r = client.get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}, r.json()

    r = client.get("/api/programs")
    assert r.status_code == 200 and len(r.json()) == 3, r.json()

    r = client.get(f"/api/programs/{showcase}/risk")
    assert r.status_code == 200
    assert any(s["risk_band"] == "HIGH" for s in r.json()["scores"]), r.json()

    r = client.get("/api/kb/search", params={"q": "thermal"})
    assert r.status_code == 200 and r.json(), r.json()

    asset_id = r.json()[0]["asset_id"]
    r = client.get(f"/api/asset/{asset_id}")
    assert r.status_code == 200 and len(r.content) > 0

    r = client.get("/api/programs/NOPE")
    assert r.status_code == 404

    print("api.main OK — health, programs, risk, kb search, asset stream, 404 all pass")
