from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

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
    graph_name: str = "commerce_data_oop",
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
    """Load TBox definitions into FalkorDB using FalkorTBoxRepository.

    This writes TBox metadata only. It does not create ABox instances.
    """

    if clear:
        try:
            graph.delete()
        except Exception as exc:  # FalkorDB raises on deleting a missing graph.
            if "empty key" not in str(exc).lower() and "not found" not in str(exc).lower():
                raise

    from .falkor_repository import FalkorTBoxRepository

    falkor_repo = FalkorTBoxRepository(graph)

    classes = repo.list_classes()
    interfaces = repo.list_interfaces()
    properties = repo.list_properties()
    relationships = repo.list_relationships()
    constraints = repo.list_constraints()

    for class_def in classes:
        falkor_repo.create_class(
            class_def.name,
            label=class_def.label,
            description=class_def.description,
            metadata=class_def.metadata,
            merge=True,
        )

    for interface_def in interfaces:
        falkor_repo.create_interface(
            interface_def.name,
            description=interface_def.description,
            metadata=interface_def.metadata,
            merge=True,
        )

    for property_def in properties:
        falkor_repo.create_property(
            property_def.name,
            datatype=property_def.datatype,
            description=property_def.description,
            metadata=property_def.metadata,
            merge=True,
        )

    implements_edges = 0
    for class_def in classes:
        for interface_def in repo.get_interfaces_of_class(class_def.name):
            falkor_repo.implement_interface(
                class_name=class_def.name, interface_name=interface_def.name
            )
            implements_edges += 1

    property_edges = 0
    for class_def in classes:
        for effective in repo.get_properties_of_class(
            class_def.name, include_interfaces=False
        ):
            binding = effective.binding
            falkor_repo.attach_property_to_class(
                class_name=class_def.name,
                property_name=effective.property.name,
                required=binding.required,
                unique=binding.unique,
                nullable=binding.nullable,
                default=binding.default,
                metadata=binding.metadata,
            )
            property_edges += 1

    for interface_def in interfaces:
        for effective in repo.get_properties_of_interface(interface_def.name):
            binding = effective.binding
            falkor_repo.attach_property_to_interface(
                interface_name=interface_def.name,
                property_name=effective.property.name,
                required=binding.required,
                unique=binding.unique,
                nullable=binding.nullable,
                default=binding.default,
                metadata=binding.metadata,
            )
            property_edges += 1

    relationship_endpoint_edges = 0
    for relationship_def in relationships:
        falkor_repo.define_relationship(
            id=relationship_def.id,
            name=relationship_def.name,
            from_class=relationship_def.from_class,
            to_class=relationship_def.to_class,
            min_count=relationship_def.min_count,
            max_count=relationship_def.max_count,
            required=relationship_def.required,
            description=relationship_def.description,
            metadata=relationship_def.metadata,
            merge=True,
        )
        relationship_endpoint_edges += 2

        for effective in repo.get_properties_of_relationship(relationship_def.id):
            binding = effective.binding
            falkor_repo.attach_property_to_relationship(
                relationship_id=relationship_def.id,
                property_name=effective.property.name,
                required=binding.required,
                unique=binding.unique,
                nullable=binding.nullable,
                default=binding.default,
                metadata=binding.metadata,
            )
            property_edges += 1

    constraint_edges = 0
    for constraint in constraints:
        falkor_repo.create_constraint(
            id=constraint.id,
            kind=constraint.kind,
            target_kind=constraint.target_kind,
            target_id=constraint.target_id,
            property_names=constraint.property_names,
            expression=constraint.expression,
            severity=constraint.severity,
            description=constraint.description,
            metadata=constraint.metadata,
            merge=True,
        )
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

