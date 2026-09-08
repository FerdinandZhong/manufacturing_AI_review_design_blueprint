"""Seeded multimodal KB assets (Task 7) — tiny deterministic PNGs + text/markdown.

Deterministic: re-running build_assets() must produce byte-identical blobs (no
randomness, no timestamps). Assets are generated in-memory only; nothing is
written to data/kb/raw/ — knowledge.kb.build_kb() is the sole consumer and it
persists everything (blob included) into data/kb/assets.lance, so a separate
on-disk copy of the raw files would just be a second, harder-to-keep-in-sync
source of truth for no benefit here (YAGNI).
"""
import sys, os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "02_backend"))

import struct
import zlib

try:
    import numpy as np
except ImportError:
    np = None

try:
    from PIL import Image
    import io as _io
except ImportError:
    Image = None


def _png_bytes(gray_value: int = 128, size: int = 8) -> bytes:
    """Tiny deterministic grayscale PNG. Uses PIL if available, else a minimal
    hand-built 1x1 gray PNG (no dependency required for the self-check to pass
    in a stripped-down environment)."""
    if Image is not None and np is not None:
        arr = np.full((size, size), gray_value, dtype=np.uint8)
        buf = _io.BytesIO()
        Image.fromarray(arr, mode="L").save(buf, format="PNG")
        return buf.getvalue()
    # Minimal 1x1 grayscale PNG, hand-assembled (no external deps).
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
    raw = bytes([0, gray_value])  # filter byte + 1 gray pixel
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


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
            "blob": _png_bytes(180),
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
            "blob": _png_bytes(140),
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
            "asset_id": "AST-ATLAS-energy-spec", "ontology_class": "SpecSheet", "modality": "pdf",
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
            "asset_id": "AST-VEGA-cost-spec", "ontology_class": "SpecSheet", "modality": "pdf",
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
            "blob": _png_bytes(90),
            "program_ref": "PACK-ATLAS-01", "linked_entity_type": "Part",
            "linked_entity_id": "BOM-ATLAS-range-01",
        },
        {
            "asset_id": "AST-VEGA-pack-photo", "ontology_class": "ComponentPhoto", "modality": "image",
            "title": "Vega battery pack module photo",
            "caption_text": "Photo of the assembled Vega battery pack thermal margin module.",
            "blob": _png_bytes(60),
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
    return assets


if __name__ == "__main__":
    a = build_assets()
    assert len(a) >= 8, len(a)
    assert all(x["blob"] for x in a)
    assert any(x["ontology_class"] == "DesignImage" and "thermal" in x["linked_entity_id"] for x in a)
    assert any(x["ontology_class"] == "TestReport" and "thermal" in x["linked_entity_id"] for x in a)
    # PNG bytes must be re-generated byte-identical (determinism check).
    assert _png_bytes(180) == _png_bytes(180)
    print(f"generate_assets OK — {len(a)} assets, classes={sorted({x['ontology_class'] for x in a})}")
