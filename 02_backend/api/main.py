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
import uuid

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

from common.db import get_connection
from common import source
from engineering import traceability
from engineering.test_bench import run_test_bench
from ml import risk_model
from knowledge import kb, ontology
from agents.supervisor import run_gate_review
from agents.tools import TOOLS

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


_MODALITY_MEDIA_TYPE = {"image": "image/png", "pdf": "application/pdf", "text": "text/plain"}
_DECISIONS = {"APPROVED", "APPROVED_WITH_CONDITIONS", "REJECTED"}


# ── programs ────────────────────────────────────────────────────────────────

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
def kb_search(q: str, cls: str | None = None, k: int = 3):
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
    return Response(content=bytes(asset["blob"]), media_type=media_type)


@app.get("/api/ontology")
def get_ontology():
    return {"classes": ontology.classes(), "relations": ontology.relations()}


# ── gate review (agents) ────────────────────────────────────────────────────

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


if __name__ == "__main__":
    from fastapi.testclient import TestClient
    from common.db import init_db
    from ml.train import train

    init_db()
    showcase = "PACK-ATLAS-01"
    for _p in ["PACK-ORION-00", "PACK-VEGA-00", showcase]:
        run_test_bench(_p)
    train()
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
