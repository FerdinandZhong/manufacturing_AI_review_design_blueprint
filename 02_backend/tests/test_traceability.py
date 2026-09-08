from engineering.traceability import coverage, decide, missing_standards

def test_coverage_reports_gap():
    cov = coverage("PACK-ATLAS-01")
    assert cov["total"] >= 5 and cov["gaps"]           # cost req uncovered
    assert 0.0 <= cov["pct"] <= 1.0

def test_decide_is_conditional_for_showcase():
    cov = coverage("PACK-ATLAS-01")
    results = [{"verdict":"PASS"},{"verdict":"MARGINAL"}]
    assert decide(cov, results, missing_standards("PACK-ATLAS-01")) == "CONDITIONAL"

def test_decide_fail_on_failing_test():
    assert decide({"pct":1.0,"gaps":[]},[{"verdict":"FAIL"}],[]) == "FAIL"
