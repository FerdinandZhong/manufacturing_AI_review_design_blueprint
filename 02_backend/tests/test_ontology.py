from knowledge import ontology

def test_ontology_classes_and_relations():
    cs = ontology.classes()
    assert {"DesignImage","SpecSheet","TestReport","ComponentPhoto","RequirementDoc"}.issubset(set(cs))
    rels = ontology.relations()
    assert any(r["from"]=="DesignImage" and r["to"]=="Requirement" for r in rels)
    assert ontology.validate_asset({"ontology_class":"DesignImage"})
    assert not ontology.validate_asset({"ontology_class":"Nonsense"})
    assert ontology.describe("TestReport")["description"]
