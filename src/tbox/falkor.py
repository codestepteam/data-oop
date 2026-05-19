from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from .models import ConstraintDef, EffectivePropertyDef, PropertyBinding
from .repository import TBoxRepository


class FalkorGraph(Protocol):
    def query(
        self,
        q: str,
        params: dict[str, object] | None = None,
        timeout: int | None = None,
    ) -> Any: ...

    def delete(self) -> None: ...


@dataclass(frozen=True)
class FalkorLoadResult:
    graph_name: str
    classes: int
    interfaces: int
    properties: int
    relationships: int
    constraints: int
    implements_edges: int
    property_edges: int
    relationship_endpoint_edges: int
    constraint_edges: int

    @property
    def nodes(self) -> int:
        return (
            self.classes
            + self.interfaces
            + self.properties
            + self.relationships
            + self.constraints
        )

    @property
    def edges(self) -> int:
        return (
            self.implements_edges
            + self.property_edges
            + self.relationship_endpoint_edges
            + self.constraint_edges
        )


def connect_and_load_tbox_to_falkor(
    repo: TBoxRepository,
    *,
    graph_name: str = "commerce_tbox",
    host: str = "localhost",
    port: int = 6380,
    username: str | None = None,
    password: str | None = None,
    clear: bool = False,
) -> FalkorLoadResult:
    """Connect to FalkorDB and load the given TBox repository into a graph."""

    from falkordb import FalkorDB

    db = FalkorDB(host=host, port=port, username=username, password=password)
    graph = db.select_graph(graph_name)
    return load_tbox_to_falkor(repo, graph=graph, graph_name=graph_name, clear=clear)


def load_tbox_to_falkor(
    repo: TBoxRepository,
    *,
    graph: FalkorGraph,
    graph_name: str = "tbox",
    clear: bool = False,
) -> FalkorLoadResult:
    """Load TBox definitions into FalkorDB using the planned graph shape.

    This writes TBox metadata only. It does not create ABox instances.
    """

    if clear:
        try:
            graph.delete()
        except Exception as exc:  # FalkorDB raises on deleting a missing graph.
            if "empty key" not in str(exc).lower() and "not found" not in str(exc).lower():
                raise

    classes = repo.list_classes()
    interfaces = repo.list_interfaces()
    properties = repo.list_properties()
    relationships = repo.list_relationships()
    constraints = repo.list_constraints()

    for class_def in classes:
        graph.query(
            """
            MERGE (n:ClassDef {name: $name})
            SET n.kind = $kind,
                n.label = $label,
                n.description = $description,
                n.metadata = $metadata
            """,
            {
                "name": class_def.name,
                "kind": class_def.kind,
                "label": class_def.label,
                "description": class_def.description,
                "metadata": _json(class_def.metadata),
            },
        )

    for interface_def in interfaces:
        graph.query(
            """
            MERGE (n:InterfaceDef {name: $name})
            SET n.description = $description,
                n.metadata = $metadata
            """,
            {
                "name": interface_def.name,
                "description": interface_def.description,
                "metadata": _json(interface_def.metadata),
            },
        )

    for property_def in properties:
        graph.query(
            """
            MERGE (n:PropertyDef {name: $name})
            SET n.datatype = $datatype,
                n.description = $description,
                n.metadata = $metadata
            """,
            {
                "name": property_def.name,
                "datatype": property_def.datatype,
                "description": property_def.description,
                "metadata": _json(property_def.metadata),
            },
        )

    implements_edges = 0
    for class_def in classes:
        for interface_def in repo.get_interfaces_of_class(class_def.name):
            graph.query(
                """
                MATCH (c:ClassDef {name: $class_name})
                MATCH (i:InterfaceDef {name: $interface_name})
                MERGE (c)-[:IMPLEMENTS]->(i)
                """,
                {"class_name": class_def.name, "interface_name": interface_def.name},
            )
            implements_edges += 1

    property_edges = 0
    for class_def in classes:
        property_edges += _load_property_edges(
            graph,
            owner_label="ClassDef",
            owner_key="name",
            owner_id=class_def.name,
            properties=repo.get_properties_of_class(
                class_def.name, include_interfaces=False
            ),
        )
    for interface_def in interfaces:
        property_edges += _load_property_edges(
            graph,
            owner_label="InterfaceDef",
            owner_key="name",
            owner_id=interface_def.name,
            properties=repo.get_properties_of_interface(interface_def.name),
        )

    relationship_endpoint_edges = 0
    for relationship_def in relationships:
        graph.query(
            """
            MERGE (r:RelationshipDef {id: $id})
            SET r.name = $name,
                r.description = $description,
                r.metadata = $metadata
            """,
            {
                "id": relationship_def.id,
                "name": relationship_def.name,
                "description": relationship_def.description,
                "metadata": _json(relationship_def.metadata),
            },
        )
        graph.query(
            """
            MATCH (r:RelationshipDef {id: $id})
            MATCH (c:ClassDef {name: $from_class})
            MERGE (r)-[edge:FROM_CLASS]->(c)
            SET edge.minCount = $min_count,
                edge.maxCount = $max_count,
                edge.required = $required
            """,
            {
                "id": relationship_def.id,
                "from_class": relationship_def.from_class,
                "min_count": relationship_def.min_count,
                "max_count": relationship_def.max_count,
                "required": relationship_def.required,
            },
        )
        graph.query(
            """
            MATCH (r:RelationshipDef {id: $id})
            MATCH (c:ClassDef {name: $to_class})
            MERGE (r)-[:TO_CLASS]->(c)
            """,
            {"id": relationship_def.id, "to_class": relationship_def.to_class},
        )
        relationship_endpoint_edges += 2
        property_edges += _load_property_edges(
            graph,
            owner_label="RelationshipDef",
            owner_key="id",
            owner_id=relationship_def.id,
            properties=repo.get_properties_of_relationship(relationship_def.id),
        )

    constraint_edges = 0
    for constraint in constraints:
        graph.query(
            """
            MERGE (c:ConstraintDef {id: $id})
            SET c.kind = $kind,
                c.targetKind = $target_kind,
                c.targetId = $target_id,
                c.propertyNames = $property_names,
                c.expression = $expression,
                c.severity = $severity,
                c.description = $description,
                c.metadata = $metadata
            """,
            {
                "id": constraint.id,
                "kind": constraint.kind,
                "target_kind": constraint.target_kind,
                "target_id": constraint.target_id,
                "property_names": list(constraint.property_names),
                "expression": constraint.expression,
                "severity": constraint.severity,
                "description": constraint.description,
                "metadata": _json(constraint.metadata),
            },
        )
        _load_constraint_edge(graph, constraint)
        constraint_edges += 1

    return FalkorLoadResult(
        graph_name=graph_name,
        classes=len(classes),
        interfaces=len(interfaces),
        properties=len(properties),
        relationships=len(relationships),
        constraints=len(constraints),
        implements_edges=implements_edges,
        property_edges=property_edges,
        relationship_endpoint_edges=relationship_endpoint_edges,
        constraint_edges=constraint_edges,
    )


def _load_property_edges(
    graph: FalkorGraph,
    *,
    owner_label: str,
    owner_key: str,
    owner_id: str,
    properties: list[EffectivePropertyDef],
) -> int:
    query = f"""
        MATCH (owner:{owner_label} {{{owner_key}: $owner_id}})
        MATCH (property:PropertyDef {{name: $property_name}})
        MERGE (owner)-[edge:HAS_PROPERTY]->(property)
        SET edge.required = $required,
            edge.unique = $unique,
            edge.nullable = $nullable,
            edge.defaultValue = $default_value,
            edge.defaultJson = $default_json,
            edge.description = $description,
            edge.metadata = $metadata
    """
    count = 0
    for effective in properties:
        binding = effective.binding
        graph.query(
            query,
            {
                "owner_id": owner_id,
                "property_name": effective.property.name,
                **_binding_params(binding),
            },
        )
        count += 1
    return count


def _load_constraint_edge(graph: FalkorGraph, constraint: ConstraintDef) -> None:
    target_label, target_key = {
        "class": ("ClassDef", "name"),
        "interface": ("InterfaceDef", "name"),
        "property": ("PropertyDef", "name"),
        "relationship": ("RelationshipDef", "id"),
    }[constraint.target_kind]
    graph.query(
        f"""
        MATCH (constraint:ConstraintDef {{id: $constraint_id}})
        MATCH (target:{target_label} {{{target_key}: $target_id}})
        MERGE (constraint)-[:CONSTRAINS]->(target)
        """,
        {"constraint_id": constraint.id, "target_id": constraint.target_id},
    )


def _binding_params(binding: PropertyBinding) -> dict[str, object]:
    return {
        "required": binding.required,
        "unique": binding.unique,
        "nullable": binding.nullable,
        "default_value": binding.default,
        "default_json": _json(binding.default),
        "description": binding.description,
        "metadata": _json(binding.metadata),
    }


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
