import hashlib
from pathlib import Path

from common import source


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "02_backend" / "data_generation" / "generate_synthetic_data.py"


def _load_generator_as_notebook_cell():
    namespace = {"__name__": "notebook_cell"}
    exec(compile(GENERATOR.read_text(), "<notebook-cell>", "exec"), namespace)
    return namespace


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


def test_generator_runs_as_notebook_cell_without_file(tmp_path, monkeypatch):
    monkeypatch.delenv("CDSW_PROJECT_HOME", raising=False)
    monkeypatch.chdir(ROOT / "02_backend")

    generator = _load_generator_as_notebook_cell()

    assert Path(generator["PROJECT_ROOT"]) == ROOT
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    generator["generate"](str(first_dir))
    generator["generate"](str(second_dir))
    for csv_path in sorted(first_dir.glob("*.csv")):
        peer = second_dir / csv_path.name
        assert peer.exists()
        assert hashlib.sha256(csv_path.read_bytes()).digest() == hashlib.sha256(peer.read_bytes()).digest()


def test_generator_uses_workbench_project_home_without_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CDSW_PROJECT_HOME", str(ROOT))

    generator = _load_generator_as_notebook_cell()

    assert Path(generator["PROJECT_ROOT"]) == ROOT
