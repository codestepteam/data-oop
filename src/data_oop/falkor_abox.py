from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .falkor import FalkorGraph
from .validator import NAME_RE


@dataclass(frozen=True)
class ABoxNodeResult:
    class_name: str
    uuid: str
    properties: dict[str, Any]


@dataclass(frozen=True)
class ABoxRelationshipResult:
    from_class: str
    from_uuid: str
    relationship_name: str
    to_class: str
    to_uuid: str
    properties: dict[str, Any]


# ABox nodes are not grouped with an :ABox label. TBox nodes are grouped with
# :TBox, while ABox nodes use only their domain class label, e.g.
# (:SalesChannel {uuid: ...}). Every concrete graph node must have uuid.
def upsert_abox_node(
    *,
    graph: FalkorGraph,
    class_name: str,
    uuid: str,
    properties: dict[str, Any] | None = None,
) -> ABoxNodeResult:
    """Create or update one ABox node for a ClassDef.

    The function validates that a matching TBox ClassDef exists, then MERGEs an
    ABox node with the domain class label only. It does not add an :ABox label.
    """

    label = _safe_identifier(class_name, "class")
    props = dict(properties or {})
    if "uuid" in props and props["uuid"] != uuid:
        raise ValueError("properties['uuid'] must match uuid argument")
    props.pop("uuid", None)

    _require_class_def(graph, class_name)
    set_clause, params = _set_clause("n", props)
    query = f"""
        MERGE (n:{label} {{uuid: $uuid}})
        SET n.uuid = $uuid{set_clause}
        RETURN n.uuid
    """
    graph.query(query, {"uuid": uuid, **params})
    return ABoxNodeResult(class_name=class_name, uuid=uuid, properties={"uuid": uuid, **props})


def connect_and_upsert_abox_node(
    *,
    graph_name: str = "commerce_data_oop",
    host: str = "localhost",
    port: int = 6380,
    username: str | None = None,
    password: str | None = None,
    class_name: str,
    uuid: str,
    properties: dict[str, Any] | None = None,
) -> ABoxNodeResult:
    """Connect to FalkorDB and create/update one ABox node."""

    from falkordb import FalkorDB

    db = FalkorDB(host=host, port=port, username=username, password=password)
    graph = db.select_graph(graph_name)
    return upsert_abox_node(
        graph=graph,
        class_name=class_name,
        uuid=uuid,
        properties=properties,
    )


def upsert_abox_relationship(
    *,
    graph: FalkorGraph,
    from_class: str,
    from_uuid: str,
    relationship_name: str,
    to_class: str,
    to_uuid: str,
    properties: dict[str, Any] | None = None,
) -> ABoxRelationshipResult:
    """Create or update an ABox relationship between two domain nodes."""

    from_label = _safe_identifier(from_class, "from_class")
    to_label = _safe_identifier(to_class, "to_class")
    rel_type = _safe_identifier(relationship_name, "relationship")
    props = dict(properties or {})
    _require_relationship_def(
        graph,
        from_class=from_class,
        relationship_name=relationship_name,
        to_class=to_class,
    )
    set_clause, params = _set_clause("r", props)
    graph.query(
        f"""
        MATCH (from_node:{from_label} {{uuid: $from_uuid}})
        MATCH (to_node:{to_label} {{uuid: $to_uuid}})
        MERGE (from_node)-[r:{rel_type}]->(to_node)
        SET r.uuid = coalesce(r.uuid, $relationship_uuid){set_clause}
        RETURN r.uuid
        """,
        {
            "from_uuid": from_uuid,
            "to_uuid": to_uuid,
            "relationship_uuid": f"{from_uuid}:{relationship_name}:{to_uuid}",
            **params,
        },
    )
    return ABoxRelationshipResult(
        from_class=from_class,
        from_uuid=from_uuid,
        relationship_name=relationship_name,
        to_class=to_class,
        to_uuid=to_uuid,
        properties=props,
    )


def _require_class_def(graph: FalkorGraph, class_name: str) -> None:
    rows = graph.query(
        "MATCH (c:TBox:ClassDef {name: $class_name}) RETURN count(c)",
        {"class_name": class_name},
    ).result_set
    if not rows or rows[0][0] != 1:
        raise ValueError(f"ClassDef not found: {class_name}")


def _require_relationship_def(
    graph: FalkorGraph,
    *,
    from_class: str,
    relationship_name: str,
    to_class: str,
) -> None:
    rows = graph.query(
        """
        MATCH (r:TBox:RelationshipDef {name: $relationship_name})-[:FROM_CLASS]->(:TBox:ClassDef {name: $from_class})
        MATCH (r)-[:TO_CLASS]->(:TBox:ClassDef {name: $to_class})
        RETURN count(r)
        """,
        {
            "from_class": from_class,
            "relationship_name": relationship_name,
            "to_class": to_class,
        },
    ).result_set
    if not rows or rows[0][0] != 1:
        raise ValueError(
            "RelationshipDef not found: "
            f"({from_class})-[:{relationship_name}]->({to_class})"
        )


def _set_clause(alias: str, properties: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    assignments: list[str] = []
    params: dict[str, Any] = {}
    for index, (key, value) in enumerate(properties.items()):
        prop = _safe_identifier(key, "property")
        param = f"prop_{index}"
        assignments.append(f", {alias}.{prop} = ${param}")
        params[param] = value
    return "".join(assignments), params


def _safe_identifier(value: str, kind: str) -> str:
    if not NAME_RE.match(value):
        raise ValueError(f"Unsafe {kind} identifier: {value}")
    return value


def clear_abox_nodes(*, graph: FalkorGraph) -> int:
    """Delete all ABox nodes (nodes that are not :TBox, :ValidationRun, or :ValidationIssue) from FalkorDB.
    
    Returns the number of deleted nodes.
    """
    # Count first to return how many we are deleting
    res = graph.query(
        "MATCH (n) WHERE NOT n:TBox AND NOT n:ValidationRun AND NOT n:ValidationIssue RETURN count(n)"
    ).result_set
    count = int(res[0][0]) if res and res[0] else 0

    if count > 0:
        # DETACH DELETE removes the nodes and their relationships
        graph.query(
            "MATCH (n) WHERE NOT n:TBox AND NOT n:ValidationRun AND NOT n:ValidationIssue DETACH DELETE n"
        )
    
    return count


def connect_and_clear_abox_nodes(
    *,
    graph_name: str = "commerce_data_oop",
    host: str = "localhost",
    port: int = 6380,
    username: str | None = None,
    password: str | None = None,
) -> int:
    """Connect to FalkorDB and delete all ABox nodes."""
    from falkordb import FalkorDB

    db = FalkorDB(host=host, port=port, username=username, password=password)
    graph = db.select_graph(graph_name)
    return clear_abox_nodes(graph=graph)
