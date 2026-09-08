"""Gate-review workers — 5 read-only agents that each fetch one data slice via
agents.tools.TOOLS (or engineering.traceability directly, for the one function
not in the registry), log an evidence row, ask the LLM for a 3-bullet finding,
and fall back to a deterministic template (with the real numbers) if the LLM
call fails — which it always will in this environment (no live endpoint
configured). Code decides (traceability.decide in supervisor.py), LLM only
narrates prose here.

Two-store rule: workers only READ (TOOLS / traceability / kb / ontology) and
write only evidence rows via common.evidence.create_evidence.
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "02_backend"))

from agents.llm_client import chat
from agents.tools import TOOLS
from common.evidence import create_evidence
from engineering.traceability import coverage, missing_standards, REQUIRED_STANDARDS

DATA_VERSION = "src-v1"


def _llm_bullets(system: str, user: str, fallback: str) -> str:
    """One non-streaming chat() call for a 3-bullet finding; on any failure
    (expected here — no live LLM endpoint), return the deterministic fallback."""
    try:
        return chat([{"role": "system", "content": system}, {"role": "user", "content": user}], stream=False)
    except Exception:
        return fallback


def run_coverage_worker(review_id: str, program_id: str) -> dict:
    matrix = TOOLS["get_traceability"](None, program_id)
    cov = coverage(program_id)
    eid = create_evidence(review_id, "get_traceability", program_id, matrix, DATA_VERSION, "coverage")
    gaps_str = ", ".join(cov["gaps"]) if cov["gaps"] else "none"
    fallback = (
        f"- Traceability coverage for {program_id}: {cov['pct'] * 100:.1f}% "
        f"({cov['traced']}/{cov['total']} requirements traced).\n"
        f"- Coverage gaps: {gaps_str}.\n"
        f"- {len(matrix['rows'])} requirements checked against design specs and test plans."
    )
    findings = _llm_bullets(
        "You are a gate-review analyst. Write exactly 3 bullet points summarizing requirement traceability coverage.",
        f"Program {program_id} traceability matrix: {matrix}\nCoverage: {cov}",
        fallback,
    )
    return {"worker": "coverage", "findings": findings, "evidence_ids": [eid]}


def run_testverdict_worker(review_id: str, program_id: str) -> dict:
    results = TOOLS["get_test_results"](None, program_id)
    eid = create_evidence(review_id, "get_test_results", program_id, results, DATA_VERSION, "testverdict")
    counts: dict[str, int] = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    flagged = [r["test_id"] for r in results if r["verdict"] in ("MARGINAL", "FAIL")]
    flagged_str = ", ".join(flagged) if flagged else "none"
    fallback = (
        f"- Test verdicts for {program_id}: {counts}.\n"
        f"- Flagged (MARGINAL/FAIL) tests: {flagged_str}.\n"
        f"- {len(results)} total test results reviewed."
    )
    findings = _llm_bullets(
        "You are a gate-review analyst. Write exactly 3 bullet points summarizing test verdicts, flagging any MARGINAL/FAIL results.",
        f"Program {program_id} test results: {results}",
        fallback,
    )
    return {"worker": "testverdict", "findings": findings, "evidence_ids": [eid]}


def run_compliance_worker(review_id: str, program_id: str) -> dict:
    missing = missing_standards(program_id)
    payload = {"required_standards": REQUIRED_STANDARDS, "missing_standards": missing}
    eid = create_evidence(review_id, "missing_standards", program_id, payload, DATA_VERSION, "compliance")
    if missing:
        fallback = (
            f"- EV-battery standards compliance for {program_id}: missing coverage for {', '.join(missing)}.\n"
            f"- Required standards: {', '.join(REQUIRED_STANDARDS)}.\n"
            f"- {len(REQUIRED_STANDARDS) - len(missing)}/{len(REQUIRED_STANDARDS)} required standards covered."
        )
    else:
        fallback = (
            f"- EV-battery standards compliance for {program_id}: all required standards covered.\n"
            f"- Required standards: {', '.join(REQUIRED_STANDARDS)}.\n"
            f"- No missing standards found."
        )
    findings = _llm_bullets(
        "You are a gate-review analyst. Write exactly 3 bullet points summarizing EV-battery standards compliance.",
        f"Program {program_id} required standards: {REQUIRED_STANDARDS}, missing: {missing}",
        fallback,
    )
    return {"worker": "compliance", "findings": findings, "evidence_ids": [eid]}


def run_designrisk_worker(review_id: str, program_id: str) -> dict:
    scores = TOOLS["get_design_risk"](None, program_id)
    explanation = TOOLS["get_model_explanation"](None)
    eid1 = create_evidence(review_id, "get_design_risk", program_id, scores, DATA_VERSION, "designrisk")
    eid2 = create_evidence(review_id, "get_model_explanation", program_id, explanation, DATA_VERSION, "designrisk")

    thermal = [s for s in scores if "thermal" in s["entity_id"].lower()]
    top_score = thermal[0] if thermal else max(scores, key=lambda s: s["risk_prob"], default=None)
    if top_score:
        risk_prob = top_score["risk_prob"]
        risk_band = top_score["risk_band"]
        entity_id = top_score["entity_id"]
        top_feature = (top_score.get("top_features") or [None])[0] or (explanation[0]["feature"] if explanation else "n/a")
    else:
        risk_prob, risk_band, entity_id = 0.0, "LOW", "n/a"
        top_feature = explanation[0]["feature"] if explanation else "n/a"

    fallback = (
        f"- Design risk assessment for {program_id}: {entity_id} scored {risk_prob:.2f} ({risk_band}), "
        f"driven primarily by {top_feature}.\n"
        f"- Model explanation top drivers: {', '.join(e['feature'] for e in explanation)}.\n"
        f"- {len(scores)} requirement(s) scored for design risk."
    )
    findings = _llm_bullets(
        "You are a gate-review analyst. Write exactly 3 bullet points summarizing design-risk model scores, "
        "calling out the highest-risk requirement and its top driving feature.",
        f"Program {program_id} risk scores: {scores}\nModel explanation: {explanation}",
        fallback,
    )
    return {"worker": "designrisk", "findings": findings, "evidence_ids": [eid1, eid2]}


def run_knowledgereuse_worker(review_id: str, program_id: str) -> dict:
    hits = TOOLS["kb_search"](None, "thermal runaway containment design", None, 3)
    eid = create_evidence(review_id, "kb_search", "thermal runaway containment design", hits, DATA_VERSION, "knowledgereuse")
    evidence_ids = [eid]

    if hits:
        top = hits[0]
        desc = TOOLS["ontology_describe"](None, top["ontology_class"])
        eid2 = create_evidence(review_id, "ontology_describe", top["ontology_class"], desc, DATA_VERSION, "knowledgereuse")
        evidence_ids.append(eid2)
        fallback = (
            f"- Knowledge reuse for {program_id}: top hit asset {top['asset_id']} "
            f"(ontology_class={top['ontology_class']}), linked to {top.get('linked_entity_id')}.\n"
            f"- Title: {top.get('title')}.\n"
            f"- {len(hits)} related asset(s) found for thermal-related design reuse."
        )
    else:
        fallback = f"- Knowledge reuse for {program_id}: no related assets found for thermal query."

    findings = _llm_bullets(
        "You are a gate-review analyst. Write exactly 3 bullet points summarizing historical knowledge-base "
        "assets relevant to this program's risk areas, citing the top asset by id and ontology class.",
        f"Program {program_id} kb hits: {hits}",
        fallback,
    )
    return {"worker": "knowledgereuse", "findings": findings, "evidence_ids": evidence_ids}


if __name__ == "__main__":
    from common.db import init_db, get_connection
    from engineering.test_bench import run_test_bench
    from ml.train import train
    from knowledge.kb import build_kb

    init_db()
    for _p in ["PACK-ORION-00", "PACK-VEGA-00", "PACK-ATLAS-01"]:
        run_test_bench(_p)
    train()
    build_kb()

    review_id, program_id = "REV-WORKERS-SELFCHECK", "PACK-ATLAS-01"
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO gate_reviews (review_id, program_id) VALUES (?, ?)",
                     (review_id, program_id))

    for fn in (run_coverage_worker, run_testverdict_worker, run_compliance_worker,
               run_designrisk_worker, run_knowledgereuse_worker):
        r = fn(review_id, program_id)
        assert set(r) == {"worker", "findings", "evidence_ids"}, r
        assert isinstance(r["findings"], str) and r["findings"], r
        assert isinstance(r["evidence_ids"], list) and r["evidence_ids"], r

    dr = run_designrisk_worker(review_id, program_id)
    assert "HIGH" in dr["findings"], dr["findings"]

    kr = run_knowledgereuse_worker(review_id, program_id)
    assert "AST-" in kr["findings"], kr["findings"]

    print("workers OK — all 5 workers returned well-shaped findings + evidence")
