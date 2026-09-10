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


# ── injection-crash regression (final review Fix 1) ────────────────────────

def test_search_tautology_filter_returns_no_rows():
    build_kb()
    hits = search("thermal", ontology_filter="' OR '1'='1", k=10)
    assert hits == []


def test_search_bare_quote_filter_does_not_raise():
    build_kb()
    hits = search("thermal", ontology_filter="'", k=10)
    assert hits == []


def test_search_valid_class_still_filters():
    build_kb()
    hits = search("thermal", ontology_filter="DesignImage", k=10)
    assert hits
    assert all(h["ontology_class"] == "DesignImage" for h in hits)


def test_get_asset_malformed_id_raises_keyerror_not_crash():
    build_kb()
    try:
        get_asset("bad'id")
        assert False, "expected KeyError"
    except KeyError:
        pass
