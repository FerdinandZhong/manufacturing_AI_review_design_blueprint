"""Synthetic source (reference) CSV generator — writes data/raw/*.csv.

Deterministic (SEED=42): re-running this script must produce byte-identical
CSVs. Source data only — never touches the SQLite ops store (see common/db.py).

Test-bench formula (Task 3, pinned here so the numbers below make sense):
    measured_value = design_spec.value          (FACTOR=1.0, no transform)
    margin = (measured_value - target_value) / target_value
    PASS if margin >= 0.10 | MARGINAL if 0 <= margin < 0.10 | FAIL if margin < 0

Showcase (PACK-ATLAS-01) thermal is pinned to margin ~= +0.03 -> MARGINAL,
everything else tested in the showcase lands margin ~= 0.15-0.25 -> PASS, and
the showcase's cost requirement is deliberately left without a test_plans row
(coverage gap). Historical PACK-ORION-00's and PACK-VEGA-00's thermal both
land margin < 0 -> FAIL (the ML label=1 seed for Task 5 — two historical
thermal FAILs give is_thermal a real correlation with the label); everything
else historical lands PASS.
"""
import sys
import os
import random
import csv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "02_backend"))

from common.config import get_config, PROJECT_ROOT as CFG_PROJECT_ROOT  # noqa: E402

random.seed(42)

CATEGORIES = ["range", "energy_density", "thermal", "safety", "cost"]
UNIT = {
    "range": "km",
    "energy_density": "Wh/kg",
    "thermal": "degC",
    "safety": "score",
    "cost": "USD/kWh",
}
PARAMETER = {
    "range": "driving_range",
    "energy_density": "pack_energy_density",
    "thermal": "thermal_margin",
    "safety": "safety_index",
    "cost": "pack_cost_index",
}
BASE_TARGET = 100.0  # same numeric target for every category/program; only the margin matters

SUPPLIERS = [
    ("SUP-01", "Northstar Cells", "APAC"),
    ("SUP-02", "Ridgeline Materials", "NA"),
    ("SUP-03", "Voltaic Components", "EU"),
    ("SUP-04", "Cascade Electronics", "NA"),
    ("SUP-05", "Meridian Alloys", "EU"),
]

# ---------------------------------------------------------------------------
# Programs
# ---------------------------------------------------------------------------

PROGRAMS = [
    {
        "program_id": "PACK-ATLAS-01",
        "name": "Atlas Battery Pack",
        "vehicle_platform": "EV-SUV-Platform-2",
        "target_market": "NA/EU",
        "stage": "GATE_REVIEW",
        "gate_status": "PENDING",
    },
    {
        "program_id": "PACK-ORION-00",
        "name": "Orion Battery Pack",
        "vehicle_platform": "EV-Sedan-Platform-1",
        "target_market": "NA",
        "stage": "COMPLETE",
        "gate_status": "APPROVED",
    },
    {
        "program_id": "PACK-VEGA-00",
        "name": "Vega Battery Pack",
        "vehicle_platform": "EV-Truck-Platform-3",
        "target_market": "NA/EU",
        "stage": "COMPLETE",
        "gate_status": "APPROVED",
    },
]

PROGRAM_SHORT = {"PACK-ATLAS-01": "ATLAS", "PACK-ORION-00": "ORION", "PACK-VEGA-00": "VEGA"}

# Per-category margin for each program (design_spec.value = BASE_TARGET * (1 + margin)).
# Showcase: literal, pinned per the docstring above. cost has no test_plan (coverage gap),
# its margin here only shapes the design_spec value (never test-benched in Phase 1).
SHOWCASE_MARGIN = {
    "range": 0.20,
    "energy_density": 0.18,
    "thermal": 0.03,   # -> MARGINAL, the showcase standout
    "safety": 0.22,
    "cost": 0.12,       # no test_plans row for this requirement
}

# Historical programs: fixed per-category base margin, with a fixed per-program
# offset on thermal so BOTH ORION's and VEGA's thermal are historical FAILs
# (Task 5's label=1 seed needs >=2 thermal rows correlated with failure so
# is_thermal carries signal); everything else historical stays a safe PASS.
HISTORICAL_BASE_MARGIN = {"range": 0.15, "energy_density": 0.15, "thermal": 0.15, "safety": 0.15, "cost": 0.15}
HISTORICAL_THERMAL_OFFSET = {"PACK-ORION-00": -0.25, "PACK-VEGA-00": -0.23}  # 0.15-0.25=-0.10, 0.15-0.23=-0.08 -> both FAIL


def _historical_margins(program_id: str) -> dict:
    margins = dict(HISTORICAL_BASE_MARGIN)
    margins["thermal"] += HISTORICAL_THERMAL_OFFSET[program_id]
    return margins


PROGRAM_MARGINS = {
    "PACK-ATLAS-01": SHOWCASE_MARGIN,
    "PACK-ORION-00": _historical_margins("PACK-ORION-00"),
    "PACK-VEGA-00": _historical_margins("PACK-VEGA-00"),
}

# Showcase: every category except cost gets a test_plans row (cost = coverage gap).
TESTED_CATEGORIES = {
    "PACK-ATLAS-01": ["range", "energy_density", "thermal", "safety"],
    "PACK-ORION-00": CATEGORIES,
    "PACK-VEGA-00": CATEGORIES,
}


def _priority(category: str) -> str:
    return "P0" if category in ("thermal", "safety") else "P1"


def build_rows():
    requirements, design_specs, bom_items, test_plans = [], [], [], []
    used_suppliers = set()

    for prog in PROGRAMS:
        pid = prog["program_id"]
        short = PROGRAM_SHORT[pid]
        margins = PROGRAM_MARGINS[pid]

        for i, category in enumerate(CATEGORIES):
            req_id = f"REQ-{short}-{category}"
            target_value = BASE_TARGET
            requirements.append({
                "req_id": req_id,
                "program_id": pid,
                "category": category,
                "text": f"{prog['name']} {category.replace('_', ' ')} requirement",
                "target_value": target_value,
                "unit": UNIT[category],
                "priority": _priority(category),
                "source": "program_charter",
                "status": "APPROVED",
            })

            spec_id = f"DS-{short}-{category}"
            value = round(target_value * (1 + margins[category]), 2)
            design_specs.append({
                "spec_id": spec_id,
                "program_id": pid,
                "req_id": req_id,
                "parameter": PARAMETER[category],
                "value": value,
                "unit": UNIT[category],
                "rationale": f"Derived from {req_id} target with program margin allowance",
                "cell_chemistry": "NMC811" if short != "VEGA" else "LFP",
                "version": "v1",
            })

            supplier_id = SUPPLIERS[(i + len(bom_items)) % len(SUPPLIERS)][0]
            used_suppliers.add(supplier_id)
            bom_items.append({
                "part_id": f"BOM-{short}-{category}-01",
                "program_id": pid,
                "spec_id": spec_id,
                "name": f"{PARAMETER[category].replace('_', ' ').title()} module",
                "supplier_id": supplier_id,
                "qty": random.randint(1, 4),
                "unit_cost": round(random.uniform(20.0, 200.0), 2),
                "mass_kg": round(random.uniform(0.5, 15.0), 2),
            })

            if category in TESTED_CATEGORIES[pid]:
                test_plans.append({
                    "test_id": f"T-{short}-{category}-01",
                    "program_id": pid,
                    "req_id": req_id,
                    "method": f"{category}_bench_test",
                    "standard": "ISO-12405" if category == "thermal" else "internal",
                    "pass_criteria": "margin >= 0.10",
                    "target_value": target_value,
                    "unit": UNIT[category],
                })

    suppliers = [
        {"supplier_id": sid, "name": name, "region": region, "quality_rating": round(random.uniform(3.0, 5.0), 1)}
        for sid, name, region in SUPPLIERS
        if sid in used_suppliers
    ]

    return PROGRAMS, requirements, design_specs, bom_items, suppliers, test_plans


TABLES = {
    "programs": ["program_id", "name", "vehicle_platform", "target_market", "stage", "gate_status"],
    "requirements": ["req_id", "program_id", "category", "text", "target_value", "unit", "priority", "source", "status"],
    "design_specs": ["spec_id", "program_id", "req_id", "parameter", "value", "unit", "rationale", "cell_chemistry", "version"],
    "bom_items": ["part_id", "program_id", "spec_id", "name", "supplier_id", "qty", "unit_cost", "mass_kg"],
    "suppliers": ["supplier_id", "name", "region", "quality_rating"],
    "test_plans": ["test_id", "program_id", "req_id", "method", "standard", "pass_criteria", "target_value", "unit"],
}


def _write_csv(path: str, columns: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def generate(out_dir: str) -> dict:
    random.seed(42)  # reseed on every call so repeated in-process runs stay byte-identical
    programs, requirements, design_specs, bom_items, suppliers, test_plans = build_rows()
    os.makedirs(out_dir, exist_ok=True)
    tables = {
        "programs": programs,
        "requirements": requirements,
        "design_specs": design_specs,
        "bom_items": bom_items,
        "suppliers": suppliers,
        "test_plans": test_plans,
    }
    for name, rows in tables.items():
        _write_csv(os.path.join(out_dir, f"{name}.csv"), TABLES[name], rows)
    return tables


if __name__ == "__main__":
    import hashlib

    cfg = get_config()
    csv_dir = os.path.join(CFG_PROJECT_ROOT, cfg.get("source", {}).get("csv_dir", "data/raw"))

    tables = generate(csv_dir)
    assert len(tables["programs"]) == 3
    assert len(tables["requirements"]) == 15
    assert len(tables["design_specs"]) == 15
    assert len(tables["test_plans"]) == 14  # showcase missing its cost row (coverage gap)
    assert len(tables["bom_items"]) == 15
    assert len(tables["suppliers"]) == 5

    atlas_thermal_spec = next(d for d in tables["design_specs"] if d["spec_id"] == "DS-ATLAS-thermal")
    atlas_thermal_test = next(t for t in tables["test_plans"] if t["test_id"] == "T-ATLAS-thermal-01")
    margin = (atlas_thermal_spec["value"] - atlas_thermal_test["target_value"]) / atlas_thermal_test["target_value"]
    assert 0 <= margin < 0.10, f"showcase thermal margin should be MARGINAL, got {margin}"

    orion_thermal_spec = next(d for d in tables["design_specs"] if d["spec_id"] == "DS-ORION-thermal")
    orion_thermal_test = next(t for t in tables["test_plans"] if t["test_id"] == "T-ORION-thermal-01")
    orion_margin = (orion_thermal_spec["value"] - orion_thermal_test["target_value"]) / orion_thermal_test["target_value"]
    assert orion_margin < 0, f"historical ORION thermal margin should be FAIL, got {orion_margin}"

    vega_thermal_spec = next(d for d in tables["design_specs"] if d["spec_id"] == "DS-VEGA-thermal")
    vega_thermal_test = next(t for t in tables["test_plans"] if t["test_id"] == "T-VEGA-thermal-01")
    vega_margin = (vega_thermal_spec["value"] - vega_thermal_test["target_value"]) / vega_thermal_test["target_value"]
    assert vega_margin < 0, f"historical VEGA thermal margin should be FAIL, got {vega_margin}"

    assert not any(t["req_id"] == "REQ-ATLAS-cost" for t in tables["test_plans"]), "cost coverage gap violated"

    def _hash_dir(d: str) -> str:
        h = hashlib.sha256()
        for name in sorted(TABLES):
            with open(os.path.join(d, f"{name}.csv"), "rb") as f:
                h.update(f.read())
        return h.hexdigest()

    first_hash = _hash_dir(csv_dir)
    generate(csv_dir)  # re-run to verify determinism
    second_hash = _hash_dir(csv_dir)
    assert first_hash == second_hash, "re-generating CSVs produced different bytes"

    print(f"synthetic data OK — 3 programs, 15 requirements, 14 test_plans, hash={first_hash[:12]}")
