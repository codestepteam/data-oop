from __future__ import annotations

from data_oop import (
    InMemoryTBoxRepository,
    apply_schema,
    export_jsonld_context,
    export_owl_turtle,
    parse_schema_spec,
)


def _repo() -> InMemoryTBoxRepository:
    repo = InMemoryTBoxRepository()
    apply_schema(
        repo,
        parse_schema_spec(
            {
                "interfaces": {
                    "Named": {"properties": {"name": {"datatype": "string", "required": True}}}
                },
                "classes": {
                    "Agent": {},
                    "Organization": {},
                    "Person": {
                        "parent": "Agent",
                        "implements": ["Named"],
                        "properties": {"age": {"datatype": "integer"}},
                    },
                },
                "relationships": {
                    "WORKS_FOR": {"from": "Person", "to": "Organization", "max_count": 1}
                },
            }
        ),
    )
    return repo


def test_owl_export_maps_core_axioms() -> None:
    turtle = export_owl_turtle(_repo())

    assert ":Person a owl:Class" in turtle
    assert "rdfs:subClassOf :Agent" in turtle
    assert "rdfs:subClassOf :Named" in turtle  # interface as superclass
    assert ":WORKS_FOR a owl:ObjectProperty" in turtle
    assert "rdfs:domain :Person" in turtle
    assert "rdfs:range :Organization" in turtle
    assert ":age a owl:DatatypeProperty" in turtle
    assert "rdfs:range xsd:integer" in turtle
    # max_count=1 -> maxCardinality restriction on the domain class
    assert 'owl:maxCardinality "1"' in turtle
    # required name binding -> minCardinality restriction
    assert "owl:onProperty :name" in turtle
    assert 'owl:minCardinality "1"' in turtle


def test_jsonld_context_coerces_types() -> None:
    context = export_jsonld_context(_repo())["@context"]

    assert context["Person"].endswith("#Person")
    assert context["age"]["@type"] == "xsd:integer"
    assert context["WORKS_FOR"]["@type"] == "@id"
    assert context["name"].endswith("#name")  # plain string property stays a bare IRI
