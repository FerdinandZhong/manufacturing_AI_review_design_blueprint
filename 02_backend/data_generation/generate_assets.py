"""Deterministic multimodal seed assets, built into Lance by build_kb().

Original SVG schematics, text excerpts, and a bundled attributed reference
photograph. No network access, timestamps, or runtime source writes.
"""
import sys, os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "02_backend"))

from pathlib import Path


def _thermal_diagram(program: str) -> bytes:
    """Original, deterministic SVG schematic; illustrative, not a simulation."""
    cells = "".join(f'<rect x="{90+c*130}" y="{125+r*100}" width="110" height="76" rx="8" fill="#e3e6ea" stroke="#6b7280"/><text x="{145+c*130}" y="{168+r*100}" text-anchor="middle" font-size="16">Module {r*4+c+1}</text>' for r in range(2) for c in range(4))
    barriers = "".join(f'<path d="M {210+c*130} 120 V 310" stroke="#e35b1f" stroke-width="8"/>' for c in range(3))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450" viewBox="0 0 800 450">'
            f'<rect width="800" height="450" fill="#f7f8fa"/><g font-family="Arial,sans-serif" fill="#1a1a2e">'
            f'<text x="36" y="45" font-size="25" font-weight="bold">{program} · Thermal containment layout</text>'
            '<text x="36" y="75" font-size="15">Synthetic demo schematic · not to scale · not measured temperature data</text>'
            f'<rect x="65" y="105" width="580" height="225" rx="15" fill="white" stroke="#1c0f43" stroke-width="3"/>{cells}{barriers}'
            '<path d="M 75 345 H 635" stroke="#059669" stroke-width="9"/>'
            '<text x="80" y="380" font-size="16" fill="#059669">Cooling plate / coolant path</text>'
            '<text x="410" y="380" font-size="16" fill="#e35b1f">Orange: cell-to-cell barriers</text>'
            '<text x="36" y="420" font-size="15">Review barrier continuity alongside the linked thermal DVP&amp;R report.</text></g></svg>').encode()


def _text_blob(text: str) -> bytes:
    return text.encode("utf-8")


def build_assets() -> list[dict]:
    """Returns ~10 deterministic seed assets spanning the ontology's asset
    classes (DesignImage, SpecSheet, TestReport, ComponentPhoto, RequirementDoc),
    across the three seeded programs. Includes a PACK-ORION-00 DesignImage +
    TestReport pair linked to REQ-ORION-thermal (the historical-reuse hit the
    KB search test targets)."""
    assets = [
        {
            "asset_id": "AST-ORION-thermal-design", "ontology_class": "DesignImage", "modality": "image",
            "title": "Orion pack thermal map — cell-to-cell containment",
            "caption_text": "Thermal runaway containment design for the Orion battery pack: "
                             "cell-to-cell barrier layout limiting thermal propagation.",
            "blob": _thermal_diagram("ORION"),
            "program_ref": "PACK-ORION-00", "linked_entity_type": "Requirement",
            "linked_entity_id": "REQ-ORION-thermal",
        },
        {
            "asset_id": "AST-ORION-thermal-report", "ontology_class": "TestReport", "modality": "text",
            "title": "Orion thermal DVP&R excerpt",
            "caption_text": "DVP&R test report excerpt: Orion pack thermal runaway containment "
                             "bench test, measured margin below target (historical FAIL).",
            "blob": _text_blob(
                "# DVP&R — PACK-ORION-00 Thermal\n\n"
                "Test: thermal_bench_test\nStandard: IEC 62660\n"
                "Result: FAIL — thermal runaway containment margin below target.\n"
                "Root cause: cell-to-cell barrier gap exceeded spec.\n"
            ),
            "program_ref": "PACK-ORION-00", "linked_entity_type": "Requirement",
            "linked_entity_id": "REQ-ORION-thermal",
        },
        {
            "asset_id": "AST-ATLAS-thermal-design", "ontology_class": "DesignImage", "modality": "image",
            "title": "Atlas pack thermal map",
            "caption_text": "Atlas battery pack thermal design: cooling channel layout and "
                             "thermal margin visualization for the showcase program.",
            "blob": _thermal_diagram("ATLAS"),
            "program_ref": "PACK-ATLAS-01", "linked_entity_type": "Requirement",
            "linked_entity_id": "REQ-ATLAS-thermal",
        },
        {
            "asset_id": "AST-ATLAS-thermal-report", "ontology_class": "TestReport", "modality": "text",
            "title": "Atlas thermal DVP&R excerpt",
            "caption_text": "DVP&R test report excerpt: Atlas pack thermal bench test, "
                             "MARGINAL verdict, small positive margin.",
            "blob": _text_blob(
                "# DVP&R — PACK-ATLAS-01 Thermal\n\n"
                "Test: thermal_bench_test\nStandard: IEC 62660\n"
                "Result: MARGINAL — thermal margin ~0.03, above zero but below the 0.10 gate.\n"
            ),
            "program_ref": "PACK-ATLAS-01", "linked_entity_type": "Requirement",
            "linked_entity_id": "REQ-ATLAS-thermal",
        },
        {
            "asset_id": "AST-ATLAS-energy-spec", "ontology_class": "SpecSheet", "modality": "text",
            "title": "Atlas pack energy density spec sheet",
            "caption_text": "Component spec sheet for the Atlas pack energy density design, "
                             "NMC811 cell chemistry, derived from program requirement.",
            "blob": _text_blob(
                "SPEC SHEET — DS-ATLAS-energy_density\nParameter: pack_energy_density\n"
                "Value: 118.0 Wh/kg\nCell chemistry: NMC811\n"
            ),
            "program_ref": "PACK-ATLAS-01", "linked_entity_type": "DesignSpec",
            "linked_entity_id": "DS-ATLAS-energy_density",
        },
        {
            "asset_id": "AST-VEGA-cost-spec", "ontology_class": "SpecSheet", "modality": "text",
            "title": "Vega pack cost index spec sheet",
            "caption_text": "Component spec sheet for the Vega pack cost index design, "
                             "supplier-sourced module cost breakdown.",
            "blob": _text_blob(
                "SPEC SHEET — DS-VEGA-cost\nParameter: pack_cost_index\nUnit: USD/kWh\n"
            ),
            "program_ref": "PACK-VEGA-00", "linked_entity_type": "DesignSpec",
            "linked_entity_id": "DS-VEGA-cost",
        },
        {
            "asset_id": "AST-ATLAS-pack-photo", "ontology_class": "ComponentPhoto", "modality": "image",
            "title": "Atlas battery pack module photo",
            "caption_text": "Photo of the assembled Atlas battery pack range module, "
                             "sourced from Northstar Cells.",
            "blob": (Path(__file__).parent / "assets/battery-pack.jpg").read_bytes(),
            "program_ref": "PACK-ATLAS-01", "linked_entity_type": "Part",
            "linked_entity_id": "BOM-ATLAS-range-01",
        },
        {
            "asset_id": "AST-VEGA-pack-photo", "ontology_class": "ComponentPhoto", "modality": "image",
            "title": "Vega battery pack module photo",
            "caption_text": "Photo of the assembled Vega battery pack thermal margin module.",
            "blob": (Path(__file__).parent / "assets/battery-pack.jpg").read_bytes(),
            "program_ref": "PACK-VEGA-00", "linked_entity_type": "Part",
            "linked_entity_id": "BOM-VEGA-thermal-01",
        },
        {
            "asset_id": "AST-ATLAS-thermal-reqdoc", "ontology_class": "RequirementDoc", "modality": "text",
            "title": "Atlas thermal requirement charter excerpt",
            "caption_text": "Source requirement document excerpt: Atlas pack thermal requirement, "
                             "program charter, priority P0.",
            "blob": _text_blob(
                "# Program Charter — PACK-ATLAS-01\n\nRequirement: REQ-ATLAS-thermal\n"
                "Target: 100.0 degC margin basis. Priority: P0.\n"
            ),
            "program_ref": "PACK-ATLAS-01", "linked_entity_type": "Requirement",
            "linked_entity_id": "REQ-ATLAS-thermal",
        },
        {
            "asset_id": "AST-VEGA-safety-reqdoc", "ontology_class": "RequirementDoc", "modality": "text",
            "title": "Vega safety requirement charter excerpt",
            "caption_text": "Source requirement document excerpt: Vega pack safety requirement, "
                             "program charter, priority P0.",
            "blob": _text_blob(
                "# Program Charter — PACK-VEGA-00\n\nRequirement: REQ-VEGA-safety\n"
                "Target: 100.0 score. Priority: P0.\n"
            ),
            "program_ref": "PACK-VEGA-00", "linked_entity_type": "Requirement",
            "linked_entity_id": "REQ-VEGA-safety",
        },
    ]
    for asset in assets:
        asset["provenance"] = "Synthetic demo artifact; not production engineering evidence."
        asset["source_url"] = ""
        asset["license_url"] = ""
        if asset["ontology_class"] == "ComponentPhoto":
            asset["title"] = asset["program_ref"].split("-")[1].title() + " module reference — BMW i3 battery pack"
            asset["caption_text"] = "Illustrative reference photograph of an exposed BMW i3 battery pack. Shows module arrangement and pack enclosure; not a photograph of the synthetic program or its supplier."
            asset["provenance"] = "RudolfSimon · November 2012 · CC BY-SA 3.0 · original photograph, unmodified. Used as an illustrative reference for this synthetic program."
            asset["source_url"] = "https://commons.wikimedia.org/wiki/File:Lithium-Ion_Battery_for_BMW_i3_-_Battery_Pack.JPG"
            asset["license_url"] = "https://creativecommons.org/licenses/by-sa/3.0/"
    return assets


if __name__ == "__main__":
    a = build_assets()
    assert len(a) >= 8, len(a)
    assert all(x["blob"] for x in a)
    assert any(x["ontology_class"] == "DesignImage" and "thermal" in x["linked_entity_id"] for x in a)
    assert any(x["ontology_class"] == "TestReport" and "thermal" in x["linked_entity_id"] for x in a)
    # Schematic bytes must be re-generated byte-identical (determinism check).
    assert _thermal_diagram("ORION") == _thermal_diagram("ORION")
    print(f"generate_assets OK — {len(a)} assets, classes={sorted({x['ontology_class'] for x in a})}")
