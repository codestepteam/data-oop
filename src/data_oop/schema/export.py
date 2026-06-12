"""Export the TBox to standard ontology formats: OWL (Turtle) and a JSON-LD context.

Mapping (pragmatic, OWL-Lite-ish):

- ``ClassDef``      → ``owl:Class`` (+ ``rdfs:label`` / ``rdfs:comment``)
- ``SUBCLASS_OF``   → ``rdfs:subClassOf``
- ``InterfaceDef``  → ``owl:Class`` annotated as an interface; a class implementing
  it becomes ``rdfs:subClassOf`` the interface class (interfaces are property
  contracts, which OWL models the same way as superclasses)
- ``PropertyDef``   → ``owl:DatatypeProperty`` with ``rdfs:range`` from the datatype
- ``RelationshipDef`` → ``owl:ObjectProperty`` with ``rdfs:domain``/``rdfs:range``;
  ``min_count``/``max_count``/``required`` become ``owl:Restriction`` axioms on the
  domain class
- a required property binding → ``owl:minCardinality 1`` restriction on the owner

Caveat: when several classes bind the same property, multiple ``rdfs:domain``
triples would mean the *intersection* of those classes under RDF semantics, so
this exporter emits ``rdfs:domain`` only for single-owner properties.
"""

from __future__ import annotations

import json
from typing import Any

from data_oop.schema.repository import TBoxRepository

DEFAULT_BASE_IRI = "http://example.org/data-oop#"

_XSD_BY_DATATYPE = {
    "string": "xsd:string",
    "str": "xsd:string",
    "integer": "xsd:integer",
    "int": "xsd:integer",
    "float": "xsd:double",
    "number": "xsd:double",
    "boolean": "xsd:boolean",
    "bool": "xsd:boolean",
    "date": "xsd:date",
    "datetime": "xsd:dateTime",
    "email": "xsd:string",
    "url": "xsd:anyURI",
    "phone": "xsd:string",
    "uuid": "xsd:string",
    "json": "xsd:string",
    "object": "xsd:string",
    "array": "xsd:string",
    "list": "xsd:string",
}


def _xsd(datatype: str) -> str | None:
    return _XSD_BY_DATATYPE.get((datatype or "").lower())


def _turtle_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def export_owl_turtle(
    repo: TBoxRepository, *, base_iri: str = DEFAULT_BASE_IRI
) -> str:
    """Serialize the TBox as an OWL ontology in Turtle."""
    lines: list[str] = [
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        f"@prefix : <{base_iri}> .",
        "",
        f"<{base_iri.rstrip('#/')}> a owl:Ontology .",
        "",
    ]

    for iface in repo.list_interfaces():
        lines.append(f":{iface.name} a owl:Class ;")
        lines.append('    rdfs:comment "interface"' + (
            f' , "{_turtle_escape(iface.description)}" .' if iface.description else " ."
        ))
        lines.append("")

    for cls in repo.list_classes():
        lines.append(f":{cls.name} a owl:Class ;")
        body: list[str] = []
        if cls.label:
            body.append(f'    rdfs:label "{_turtle_escape(cls.label)}"')
        if cls.description:
            body.append(f'    rdfs:comment "{_turtle_escape(cls.description)}"')
        for parent in repo.get_superclasses(cls.name, transitive=False):
            body.append(f"    rdfs:subClassOf :{parent.name}")
        for iface in repo.get_interfaces_of_class(cls.name):
            body.append(f"    rdfs:subClassOf :{iface.name}")
        # Required property bindings become minCardinality restrictions.
        for effective in repo.get_properties_of_class(cls.name):
            if effective.binding.required:
                body.append(
                    "    rdfs:subClassOf [ a owl:Restriction ; "
                    f"owl:onProperty :{effective.property.name} ; "
                    'owl:minCardinality "1"^^xsd:nonNegativeInteger ]'
                )
        if body:
            lines.append(" ;\n".join(body) + " .")
        else:
            lines[-1] = f":{cls.name} a owl:Class ."
        lines.append("")

    # Datatype properties: domain only when a single class binds the property.
    owners_by_property: dict[str, list[str]] = {}
    for cls in repo.list_classes():
        for effective in repo.get_properties_of_class(cls.name, include_interfaces=False):
            owners_by_property.setdefault(effective.property.name, []).append(cls.name)

    for prop in repo.list_properties():
        lines.append(f":{prop.name} a owl:DatatypeProperty ;")
        body = []
        xsd_type = _xsd(prop.datatype)
        if xsd_type:
            body.append(f"    rdfs:range {xsd_type}")
        owners = owners_by_property.get(prop.name, [])
        if len(owners) == 1:
            body.append(f"    rdfs:domain :{owners[0]}")
        if prop.description:
            body.append(f'    rdfs:comment "{_turtle_escape(prop.description)}"')
        if body:
            lines.append(" ;\n".join(body) + " .")
        else:
            lines[-1] = f":{prop.name} a owl:DatatypeProperty ."
        lines.append("")

    for rel in repo.list_relationships():
        lines.append(f":{rel.name} a owl:ObjectProperty ;")
        body = [
            f"    rdfs:domain :{rel.from_class}",
            f"    rdfs:range :{rel.to_class}",
        ]
        if rel.description:
            body.append(f'    rdfs:comment "{_turtle_escape(rel.description)}"')
        lines.append(" ;\n".join(body) + " .")

        min_count = max(rel.min_count, 1 if rel.required else 0)
        if min_count > 0:
            lines.append(
                f":{rel.from_class} rdfs:subClassOf [ a owl:Restriction ; "
                f"owl:onProperty :{rel.name} ; "
                f'owl:minCardinality "{min_count}"^^xsd:nonNegativeInteger ] .'
            )
        if rel.max_count is not None:
            lines.append(
                f":{rel.from_class} rdfs:subClassOf [ a owl:Restriction ; "
                f"owl:onProperty :{rel.name} ; "
                f'owl:maxCardinality "{rel.max_count}"^^xsd:nonNegativeInteger ] .'
            )
        lines.append("")

    return "\n".join(lines)


def export_jsonld_context(
    repo: TBoxRepository, *, base_iri: str = DEFAULT_BASE_IRI
) -> dict[str, Any]:
    """Build a JSON-LD ``@context`` for the TBox vocabulary.

    Classes and interfaces map to their IRIs; datatype properties carry an
    ``@type`` coercion when the datatype has an XSD mapping; relationships are
    ``@type: @id`` (object references).
    """
    context: dict[str, Any] = {
        "@vocab": base_iri,
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "uuid": "@id",
    }
    for cls in repo.list_classes():
        context[cls.name] = f"{base_iri}{cls.name}"
    for iface in repo.list_interfaces():
        context[iface.name] = f"{base_iri}{iface.name}"
    for prop in repo.list_properties():
        xsd_type = _xsd(prop.datatype)
        if xsd_type and xsd_type != "xsd:string":
            context[prop.name] = {"@id": f"{base_iri}{prop.name}", "@type": xsd_type}
        else:
            context[prop.name] = f"{base_iri}{prop.name}"
    for rel in repo.list_relationships():
        context[rel.name] = {"@id": f"{base_iri}{rel.name}", "@type": "@id"}
    return {"@context": context}


def export_jsonld_context_str(
    repo: TBoxRepository, *, base_iri: str = DEFAULT_BASE_IRI
) -> str:
    return json.dumps(
        export_jsonld_context(repo, base_iri=base_iri), indent=2, ensure_ascii=False
    )
