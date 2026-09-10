import pytest
from fastapi.testclient import TestClient

from common.db import init_db
from engineering.test_bench import run_test_bench
from ml.train import train
from knowledge.kb import build_kb

SHOWCASE = "PACK-ATLAS-01"


@pytest.fixture(scope="module", autouse=True)
def _seed():
    """One-time seed so the API has data to read (mirrors other test modules'
    setup): ops schema + test_results for all programs, trained risk model,
    and a built KB."""
    init_db()
    for p in ["PACK-ORION-00", "PACK-VEGA-00", SHOWCASE]:
        run_test_bench(p)
    train()
    build_kb()


@pytest.fixture(scope="module")
def client():
    from api.main import app
    return TestClient(app)


# ── Step 1 floor: brief's 4 minimum checks ─────────────────────────────────

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_programs_returns_three(client):
    r = client.get("/api/programs")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_risk_has_a_high(client):
    r = client.get(f"/api/programs/{SHOWCASE}/risk")
    assert r.status_code == 200
    body = r.json()
    bands = {s["risk_band"] for s in body["scores"]}
    assert "HIGH" in bands, body


def test_kb_search_thermal_non_empty(client):
    r = client.get("/api/kb/search", params={"q": "thermal"})
    assert r.status_code == 200
    hits = r.json()
    assert hits


def test_asset_returns_bytes(client):
    hits = build_kb() and None  # ensure built; ignore return
    from knowledge.kb import search
    asset_id = search("thermal", k=1)[0]["asset_id"]
    r = client.get(f"/api/asset/{asset_id}")
    assert r.status_code == 200
    assert len(r.content) > 0


# ── extra coverage beyond the floor ────────────────────────────────────────

def test_get_program_envelope(client):
    r = client.get(f"/api/programs/{SHOWCASE}")
    assert r.status_code == 200
    body = r.json()
    assert body["program"]["program_id"] == SHOWCASE
    assert "coverage" in body and "matrix" in body


def test_get_program_404_for_unknown(client):
    r = client.get("/api/programs/NOPE-DOES-NOT-EXIST")
    assert r.status_code == 404


def test_requirements_design_bom_tests(client):
    for suffix in ("requirements", "design", "bom", "tests"):
        r = client.get(f"/api/programs/{SHOWCASE}/{suffix}")
        assert r.status_code == 200, suffix
        assert r.json(), suffix


def test_results_endpoint(client):
    r = client.get(f"/api/programs/{SHOWCASE}/results")
    assert r.status_code == 200
    assert r.json()


def test_matrix_endpoint(client):
    r = client.get(f"/api/programs/{SHOWCASE}/matrix")
    assert r.status_code == 200
    assert r.json()["program_id"] == SHOWCASE


def test_testbench_endpoint_idempotent(client):
    r1 = client.post(f"/api/programs/{SHOWCASE}/testbench")
    r2 = client.post(f"/api/programs/{SHOWCASE}/testbench")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()


def test_ontology_endpoint(client):
    r = client.get("/api/ontology")
    assert r.status_code == 200
    body = r.json()
    assert body["classes"] and body["relations"]


def test_kb_search_with_ontology_filter(client):
    r = client.get("/api/kb/search", params={"q": "thermal", "cls": "DesignImage"})
    assert r.status_code == 200


def test_asset_404_for_unknown(client):
    r = client.get("/api/asset/NOPE-DOES-NOT-EXIST")
    assert r.status_code == 404


# ── injection-crash regression (final review Fix 1) ────────────────────────

def test_kb_search_malformed_cls_does_not_500(client):
    r = client.get("/api/kb/search", params={"q": "thermal", "cls": "'"})
    assert r.status_code == 200
    assert r.json() == []


def test_asset_malformed_id_returns_404_not_500(client):
    r = client.get("/api/asset/bad'id")
    assert r.status_code == 404


def test_gate_review_stream_and_decision(client):
    review_id = "REV-API-SELFCHECK"
    with client.stream("GET", f"/api/review/{SHOWCASE}/stream", params={"review_id": review_id}) as r:
        assert r.status_code == 200
        events = [line for line in r.iter_lines() if line.startswith("data: ")]
    assert events, "expected at least one SSE event"
    assert '"type": "done"' in events[-1] or '"type":"done"' in events[-1]

    r = client.post(
        f"/api/review/{review_id}/decision",
        json={"decision": "APPROVED_WITH_CONDITIONS", "rationale": "ok", "adjudicator": "tester"},
    )
    assert r.status_code == 200

    r = client.post(
        f"/api/review/{review_id}/decision",
        json={"decision": "NOT_A_REAL_DECISION"},
    )
    assert r.status_code in (400, 422)


def test_decision_404_for_unknown_review_id(client):
    """Regression guard: a nonexistent review_id must 404, not 500 from an
    unhandled FK IntegrityError on the annotations INSERT."""
    r = client.post(
        "/api/review/REV-DOES-NOT-EXIST/decision",
        json={"decision": "APPROVED", "rationale": "n/a", "adjudicator": "tester"},
    )
    assert r.status_code == 404
