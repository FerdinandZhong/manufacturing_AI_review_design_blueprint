import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yaml

_ONTOLOGY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ontology.yaml")
_cache = None

def load_ontology() -> dict:
    global _cache
    if _cache is None:
        with open(_ONTOLOGY_PATH) as f:
            _cache = yaml.safe_load(f)
    return _cache

def classes() -> list:
    return list(load_ontology()["classes"])

def relations() -> list:
    return load_ontology()["relations"]

def describe(cls: str) -> dict:
    return load_ontology()["classes"][cls]

def validate_asset(asset: dict) -> bool:
    return asset.get("ontology_class") in classes()

if __name__ == "__main__":
    cs = classes()
    assert len(cs) >= 5
    assert validate_asset({"ontology_class": "DesignImage"})
    print("ontology OK", cs)
