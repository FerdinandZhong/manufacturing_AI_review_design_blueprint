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



def review_summary(program_id, findings, recommendation, context):
    """Render immutable review facts; scores add context and never select the gate."""
    if context is None:
        return (f"Gate review for {program_id}: recommendation {recommendation}. "
                f"{len(findings)} of 5 findings collected. "
                "The recommendation comes from deterministic engineering checks.")
    cov, results, missing = context['coverage'], context['results'], context['missing_standards']
    counts = {v:sum(r['verdict']==v for r in results) for v in ('PASS','MARGINAL','FAIL')}
    parts = ['1. Release recommendation', f'Gate review for {program_id}: recommendation {recommendation}.',
             '2. Why this result',
             f"{cov['traced']} of {cov['total']} requirements have design and test links ({cov['pct']*100:.1f}% coverage).",
             f"Validation results: {counts['PASS']} PASS, {counts['MARGINAL']} MARGINAL, {counts['FAIL']} FAIL."]
    reasons=[]
    if recommendation=='FAIL':
        if counts['FAIL']:
            reasons.append(f"{counts['FAIL']} failed validation tests")
        if cov['pct']<0.6:
            reasons.append('requirement coverage below 60%')
    elif recommendation=='CONDITIONAL':
        if counts['MARGINAL']:
            reasons.append(f"{counts['MARGINAL']} marginal validation result(s)")
        if cov['gaps']:
            reasons.append(f"{len(cov['gaps'])} requirements with incomplete coverage")
        if missing:
            reasons.append(f"{len(missing)} missing required standard(s)")
    if reasons:
        parts.insert(3, 'The recommendation is driven by '+', '.join(reasons)+'.')
    flagged = sorted(r['test_id'] for r in results if r['verdict']!='PASS')
    if flagged:
        parts.append('Tests needing attention: '+', '.join(flagged)+'.')
    if cov['gaps']:
        parts.append(f"{len(cov['gaps'])} requirements still need complete design and test links; inspect Coverage findings for their IDs.")
    parts.append('Missing test-plan standards: '+', '.join(missing)+'.' if missing else 'All required standards are linked in the test plans; this is a coverage check, not certification.')
    parts.append('3. Model and evidence context')
    assessments = {f['worker']:f.get('assessment') for f in findings}
    risk = assessments.get('designrisk')
    if risk and risk['score'] is not None:
        parts.append(f"The model flags {risk['high_risk_requirements']} of {risk['scored_requirements']} scored requirements as HIGH risk. "
                     f"The highest-scored requirement is {risk['entity_id']}, with a {risk['score']*100:.1f}% predicted risk score ({risk['risk_band']}).")
        parts.append('This small synthetic model is uncalibrated; the risk score does not measure confidence in accuracy and does not enter the gate rule.')
    else:
        parts.append('ML risk scoring was unavailable for this review; no model confidence is inferred.')
    retrieval = assessments.get('knowledgereuse')
    if retrieval and retrieval['hits']:
        hit = retrieval['hits'][0]
        parts.append(f"Retrieved {len(retrieval['hits'])} supporting sources. The strongest match is {hit['title']} [{hit['asset_id']}], "
                     f"with relevance {hit['score']:.3f} on a 0–1 scale.")
        parts.append('Retrieval relevance measures query matching. External sources and unverified OCR provide supplementary context; they do not validate Atlas performance.')
    else:
        parts.append('No supporting retrieval matches were available; the recommendation uses structured engineering records.')
    parts.append('4. Next action')
    issues = sorted((i for i in context.get('issues',[]) if i['status']!='CLOSED'), key=lambda i:i['issue_id'])
    for issue in issues:
        parts.append(f"{issue['owner']}: {issue['corrective_action']}. Verification test: {issue['verification_test_id']} [{issue['issue_id']}].")
    if counts['FAIL'] or counts['MARGINAL']:
        parts.append('Resolve the flagged validation results and record follow-up test evidence.')
    if cov['gaps']:
        parts.append('Complete the missing design/test links and execute the remaining validation work.')
    if missing:
        parts.append('Add the missing required standards to the validation plans.')
    if recommendation=='PASS':
        parts.append('The computed release checks are satisfied. Submit the evidence for a recorded human gate decision.')
    else:
        parts.append('Re-run the review after addressing these conditions. Final release approval requires a recorded human decision.')
    errors=sorted(f['worker'] for f in findings if f.get('findings','').startswith('Error:'))
    if errors:
        parts.append('Review workers unavailable: '+', '.join(errors)+'. Inspect the retained evidence before deciding.')
    return '\n'.join(parts)


def narrate(program_id: str, findings: list[dict], recommendation: str, context: dict | None = None) -> Iterator[str]:
    combined = "\n\n".join(
        f"[{f['worker'].upper()} WORKER]\n{f['findings']}" for f in sorted(findings, key=lambda x: x["worker"])
    )
    user = f"Program: {program_id}\nRecommendation: {recommendation}\n\n{combined}"
    messages = [{"role": "system", "content": _NARRATIVE_SYSTEM}, {"role": "user", "content": user}]
    fallback = review_summary(program_id, findings, recommendation, context)
    messages[0]['content'] += ' Reproduce the authoritative answer exactly: ' + fallback
    try:
        # Buffer a bounded response before validation. Never yield unvalidated tokens.
        generated = chat(messages, stream=False)
        from knowledge.narration_guard import validate_narration
        validated = validate_narration(generated, fallback)
        if f"Gate review for {program_id}: recommendation {recommendation}." not in validated:
            raise ValueError('Narration omitted the code-decided recommendation')
        # Every factual statement must survive, even if the model reorders them.
        import re
        statements = lambda text: {re.sub(r'\s+', ' ', part).strip() for part in re.split(r'\n|(?<=\.)\s+', text) if part.strip()}
        if statements(validated) != statements(fallback):
            raise ValueError('Narration omitted required review findings')
        yield validated
    except Exception:
        yield fallback


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
