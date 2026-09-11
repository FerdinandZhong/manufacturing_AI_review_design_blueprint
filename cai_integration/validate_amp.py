"""Validate the local AMP manifest before importing it into Cloudera AI."""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / ".project-metadata.yaml"
PROJECT = ROOT / "project.yaml"
REQUIRED_TASKS = {
    "Install Dependencies": "run_session",
    "Generate Synthetic Data": "run_session",
    "Prepare Data, Model & KB": "run_session",
    "Verify Prepared Demo": "run_session",
    "Vehicle NPI Platform": "start_application",
}
TASK_ORDER = [*REQUIRED_TASKS]


def validate(path: Path = METADATA, project_path: Path = PROJECT) -> dict:
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict), "AMP metadata must be a YAML mapping"
    for key in ("name", "description", "author", "specification_version", "runtimes", "tasks"):
        assert data.get(key), f"Missing AMP field: {key}"
    assert any(r.get("kernel") == "Python 3.11" for r in data["runtimes"]), "Python 3.11 runtime required"
    tasks = {task.get("name"): task for task in data["tasks"]}
    assert set(REQUIRED_TASKS) <= set(tasks), f"Missing AMP tasks: {set(REQUIRED_TASKS) - set(tasks)}"
    for name, expected_type in REQUIRED_TASKS.items():
        task = tasks[name]
        assert task.get("type") == expected_type, f"{name} must be {expected_type}"
        script = task.get("script")
        assert isinstance(script, str) and (ROOT / script).is_file(), f"Missing task script: {script}"
        assert int(task.get("cpu", 0)) > 0 and int(task.get("memory", 0)) > 0, f"{name} needs resources"
    ordered_names = [task.get("name") for task in data["tasks"]]
    positions = [ordered_names.index(name) for name in TASK_ORDER]
    assert positions == sorted(positions), "AMP tasks must run install → generate → prepare → verify → app"
    app = tasks["Vehicle NPI Platform"]
    assert app.get("subdomain") == "vehicle-npi-platform"
    assert app.get("environment_variables", {}).get("TASK_TYPE", {}).get("default") == "START_APPLICATION"
    assert app["environment_variables"]["BACKEND_PORT"]["default"] != "${CDSW_APP_PORT}"
    project = yaml.safe_load(project_path.read_text())
    assert isinstance(project, dict), "project.yaml must be a YAML mapping"
    assert project.get("api_version") == "vehicle-npi.cloudera.ai/v1"
    assert project.get("kind") == "ClouderaAIProject"
    assert project.get("metadata", {}).get("amp_manifest") == ".project-metadata.yaml"
    assert project["metadata"].get("name") == data["name"], "Project and AMP names must agree"
    project_app = project.get("spec", {}).get("application", {})
    assert project_app.get("script") == app["script"], "Project and AMP app scripts must agree"
    assert project_app.get("subdomain") == app["subdomain"], "Project and AMP subdomains must agree"
    assert project_app.get("environment", {}).get("BACKEND_PORT") == app["environment_variables"]["BACKEND_PORT"]["default"]
    expected_preparation = [tasks[name]["script"] for name in TASK_ORDER[:-1]]
    assert project.get("spec", {}).get("preparation") == expected_preparation, "Project preparation sequence must agree with AMP"
    return data


if __name__ == "__main__":
    manifest = validate()
    assert manifest["name"] == "Vehicle NPI Blueprint"
    print(f"AMP metadata OK — {len(manifest['tasks'])} tasks")
