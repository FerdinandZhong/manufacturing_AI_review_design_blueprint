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


def test_external_collection_excludes_fixtures_and_collapses_reused_photo():
    build_kb()
    all_hits = search("battery cell published experiment thermal", k=1000)
    references = [h for h in all_hits if h.get("source_url") and h.get("license_url")]
    assert len(references) == 8  # Five canonical photos plus three research assets.
    hits = search("battery cell published experiment thermal", k=30, external_only=True)
    assert len(hits) == 8
    assert all(h["source_url"] and h["license_url"] for h in hits)
    assert sum("BMW_i3" in h["source_url"] for h in hits) == 1
    assert {h["asset_id"] for h in hits if h["asset_id"].startswith("REF-")} == {
        "REF-bmw-pack", "REF-leaf-pack", "REF-cylindrical-cell", "REF-leaf-modules", "REF-leaf-cutaway"}
    assert all(h["program_ref"] == "EXTERNAL-REFERENCE" for h in hits if h["asset_id"].startswith("REF-"))
    assert search("battery", ontology_filter="TestReport", external_only=True) == []


def test_reference_photo_checksums_and_lance_bytes():
    import hashlib
    import json
    from pathlib import Path
    from PIL import Image
    import io
    root = Path(__file__).parents[1] / "data_generation/assets/references"
    manifest = json.loads((root / "manifest.json").read_text())
    build_kb()
    for item in manifest["assets"]:
        stored = get_asset(item["asset_id"])
        assert hashlib.sha256(stored["blob"]).hexdigest() == item["sha256"]
        assert stored["blob"] == (root / item["file"]).read_bytes()
        assert Image.open(io.BytesIO(stored["blob"])).size == (item["width"], item["height"])


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
