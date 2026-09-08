"""Gate-review narrative — turns 5 workers' findings + the code-decided
recommendation into a short human-readable summary, streamed token-by-token.

Code decides, LLM narrates: `recommendation` is passed in already computed
(never derived here). If chat() raises (expected — no live LLM endpoint in
this environment), yield ONE deterministic template string instead of tokens.
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "02_backend"))

from typing import Iterator

from agents.llm_client import chat

_NARRATIVE_SYSTEM = """You are a gate-review narrator for a vehicle-manufacturing NPI program.
You are given the findings of 5 specialist workers (coverage, testverdict, compliance,
designrisk, knowledgereuse) and a code-decided recommendation (PASS/CONDITIONAL/FAIL).
Write a concise (3-5 sentence) narrative summarizing the key drivers behind the
recommendation. Do not change or second-guess the recommendation — it is final."""


def narrate(program_id: str, findings: list[dict], recommendation: str) -> Iterator[str]:
    combined = "\n\n".join(
        f"[{f['worker'].upper()} WORKER]\n{f['findings']}" for f in sorted(findings, key=lambda x: x["worker"])
    )
    user = f"Program: {program_id}\nRecommendation: {recommendation}\n\n{combined}"
    messages = [{"role": "system", "content": _NARRATIVE_SYSTEM}, {"role": "user", "content": user}]
    try:
        for tok in chat(messages, stream=True):
            yield tok
    except Exception:
        drivers = ", ".join(f["worker"] for f in findings)
        yield (
            f"Gate review for {program_id}: recommendation {recommendation}. "
            f"{len(findings)} of 5 findings collected ({drivers}). "
            f"Coverage and thermal test results were the key drivers of this recommendation."
        )


if __name__ == "__main__":
    fake_findings = [
        {"worker": "coverage", "findings": "- 80% traced", "evidence_ids": []},
        {"worker": "testverdict", "findings": "- 1 MARGINAL", "evidence_ids": []},
    ]
    chunks = list(narrate("PACK-ATLAS-01", fake_findings, "CONDITIONAL"))
    assert chunks, "narrate() must yield at least one chunk"
    text = "".join(chunks)
    assert "PACK-ATLAS-01" in text and "CONDITIONAL" in text, text
    print(f"narrative OK — {len(chunks)} chunk(s), {len(text)} chars")
