from common import source

def test_showcase_program_and_children_present():
    p = source.get_program("PACK-ATLAS-01")
    assert p and p["name"]
    reqs = source.list_requirements("PACK-ATLAS-01")
    cats = {r["category"] for r in reqs}
    assert {"range","energy_density","thermal","safety","cost"}.issubset(cats)
    assert any(r["req_id"] for r in reqs)
    assert source.list_test_plans("PACK-ATLAS-01")            # has some tests
    assert source.list_design_specs("PACK-ATLAS-01")
    assert len(source.list_programs()) == 3
    assert source.historical_requirements()                   # non-showcase reqs exist

def test_one_requirement_has_no_test_plan():
    reqs = {r["req_id"] for r in source.list_requirements("PACK-ATLAS-01")}
    tested = {t["req_id"] for t in source.list_test_plans("PACK-ATLAS-01")}
    assert reqs - tested, "expected at least one uncovered requirement (coverage gap)"
