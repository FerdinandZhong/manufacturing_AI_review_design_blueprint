from knowledge.kb import build_kb, search, get_asset

def test_kb_builds_validates_and_thermal_query_hits():
    n = build_kb()
    assert n >= 8
    hits = search("thermal runaway containment design", k=3)
    assert hits and any("thermal" in (h.get("linked_entity_id") or "") for h in hits)
    top = hits[0]
    a = get_asset(top["asset_id"])
    assert a["blob"] and a["modality"] in {"image","pdf","text"}

def test_search_is_deterministic():
    build_kb()
    a = [h["asset_id"] for h in search("thermal", k=3)]
    b = [h["asset_id"] for h in search("thermal", k=3)]
    assert a == b
