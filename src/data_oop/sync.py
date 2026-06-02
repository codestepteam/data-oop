"""Materialize source-backed classes: run their bound RDB query and turn each
result row into one aggregate/segment ABox node.

Raw source rows never enter the graph — only the aggregates the query produces do.
Node identity uses a freshly generated uuid (the library's ABox convention), so
re-sync is made idempotent by ``prune``-then-insert rather than by a stable key.

The fetch loop fails fast on bad SQL: a NULL key column or a duplicate key tuple
raises before anything is written, turning silent aggregate corruption (a wrong
GROUP BY collapsing rows) into a loud, actionable error.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .connectors import fetch_rows
from .exceptions import TBoxError, TBoxNotFoundError
from .falkor import FalkorGraph
from .falkor_abox import _require_relationship_def, _safe_identifier, upsert_abox_node
from .models import MaterializeResult, SourceBinding, SourceLink
from .repository import TBoxRepository

# Reserved bookkeeping properties written onto every materialized node. NAME_RE forbids a
# leading underscore, so these are letter-led; treat them as reserved on source-backed classes.
SYNCED_AT_PROP = "synced_at"
SOURCE_CONNECTOR_PROP = "source_connector"


def materialize_source(
    *,
    repo: TBoxRepository,
    graph: FalkorGraph,
    class_name: str,
    prune: bool = True,
    now: str | None = None,
) -> MaterializeResult:
    """Run the source query bound to ``class_name`` and materialize its rows as ABox nodes.

    With ``prune=True`` (default) every node previously materialized for this class from the
    same connector is deleted first, so re-sync replaces rather than accumulates.
    """
    binding = repo.get_source_binding(class_name)
    if binding is None:
        raise TBoxNotFoundError(f"No source binding for class: {class_name}")
    if binding.materialization != "materialized":
        raise TBoxError(
            f"Source binding for {class_name!r} is {binding.materialization!r}, not materialized"
        )
    connector = repo.get_connector(binding.connector_name)
    if connector is None:
        raise TBoxNotFoundError(f"ConnectorDef not found: {binding.connector_name}")

    rows = fetch_rows(connector, binding.sql)
    mapped = _map_and_guard(rows, binding)

    synced_at = now or datetime.now(timezone.utc).isoformat()
    label = _safe_identifier(class_name, "class")

    nodes_pruned = 0
    if prune:
        nodes_pruned = _prune(graph, label, connector.name)

    edges_upserted = 0
    links_missing = 0
    for props, row in zip(mapped, rows):
        node_uuid = str(uuid4())
        # Bulk materialization may upsert thousands of rows; do not fire triggers
        # per row or a single sync could fan out into a trigger storm.
        upsert_abox_node(
            graph=graph,
            class_name=class_name,
            uuid=node_uuid,
            properties={**props, SYNCED_AT_PROP: synced_at, SOURCE_CONNECTOR_PROP: connector.name},
            fire_triggers=False,
        )
        for link in binding.links:
            created = _materialize_link(
                graph,
                source_class=class_name,
                source_uuid=node_uuid,
                link=link,
                value=row.get(link.local_key),
            )
            if created:
                edges_upserted += created
            else:
                links_missing += 1

    return MaterializeResult(
        class_name=class_name,
        connector_name=connector.name,
        rows_fetched=len(rows),
        nodes_upserted=len(mapped),
        nodes_pruned=nodes_pruned,
        synced_at=synced_at,
        edges_upserted=edges_upserted,
        links_missing=links_missing,
    )


def _materialize_link(
    graph: FalkorGraph,
    *,
    source_class: str,
    source_uuid: str,
    link: SourceLink,
    value: Any,
) -> int:
    """MERGE one edge from the freshly synced node to an existing target node.

    The target is matched by ``link.target_property == value``. Returns the number of
    edges touched (0 means the target node was not found — the link is skipped, not fatal).
    """
    if value is None:
        return 0
    source_label = _safe_identifier(source_class, "class")
    target_label = _safe_identifier(link.to_class, "to_class")
    rel_type = _safe_identifier(link.relationship_name, "relationship")
    target_prop = _safe_identifier(link.target_property or link.local_key, "property")

    if link.direction == "out":
        from_class, to_class = source_class, link.to_class
        pattern = f"(s)-[r:{rel_type}]->(t)"
        rel_uuid = "$src + ':' + $rel + ':' + t.uuid"
    else:
        from_class, to_class = link.to_class, source_class
        pattern = f"(s)<-[r:{rel_type}]-(t)"
        rel_uuid = "t.uuid + ':' + $rel + ':' + $src"

    # The relationship must be a defined TBox edge in the orientation we are creating.
    _require_relationship_def(
        graph,
        from_class=from_class,
        relationship_name=link.relationship_name,
        to_class=to_class,
    )

    result = graph.query(
        f"""
        MATCH (s:{source_label} {{uuid: $src}})
        MATCH (t:{target_label} {{{target_prop}: $val}})
        MERGE {pattern}
        SET r.uuid = coalesce(r.uuid, {rel_uuid})
        RETURN count(r)
        """,
        {"src": source_uuid, "val": value, "rel": link.relationship_name},
    ).result_set
    return int(result[0][0]) if result and result[0] else 0


def _map_and_guard(
    rows: list[dict[str, Any]], binding: SourceBinding
) -> list[dict[str, Any]]:
    """Validate keys and rename columns, returning per-row property dicts.

    Raises ``ValueError`` on a NULL key column or a duplicate key tuple — both signal a
    broken query (missing/incorrect GROUP BY) that would otherwise corrupt aggregates.
    """
    seen: set[tuple[Any, ...]] = set()
    mapped: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        key = tuple(row.get(column) for column in binding.key_columns)
        if any(value is None for value in key):
            raise ValueError(
                f"sync({binding.class_name}): NULL key column in row {index} "
                f"(key_columns={binding.key_columns}); fix the GROUP BY/SELECT"
            )
        if key in seen:
            raise ValueError(
                f"sync({binding.class_name}): duplicate key {key} in row {index}; "
                f"SQL does not yield unique key_columns={binding.key_columns}"
            )
        seen.add(key)
        mapped.append(
            {binding.column_map.get(column, column): value for column, value in row.items()}
        )
    return mapped


def _prune(graph: FalkorGraph, label: str, connector_name: str) -> int:
    count_rows = graph.query(
        f"MATCH (n:{label}) WHERE n.{SOURCE_CONNECTOR_PROP} = $conn RETURN count(n)",
        {"conn": connector_name},
    ).result_set
    count = int(count_rows[0][0]) if count_rows and count_rows[0] else 0
    if count:
        graph.query(
            f"MATCH (n:{label}) WHERE n.{SOURCE_CONNECTOR_PROP} = $conn DETACH DELETE n",
            {"conn": connector_name},
        )
    return count


def connect_and_materialize_source(
    *,
    graph_name: str = "data_oop",
    host: str = "localhost",
    port: int = 6380,
    username: str | None = None,
    password: str | None = None,
    class_name: str,
    prune: bool = True,
) -> MaterializeResult:
    """Connect to FalkorDB and materialize one source-backed class."""
    from falkordb import FalkorDB

    from .falkor_repository import FalkorTBoxRepository

    db = FalkorDB(host=host, port=port, username=username, password=password)
    graph = db.select_graph(graph_name)
    repo = FalkorTBoxRepository(graph)
    return materialize_source(repo=repo, graph=graph, class_name=class_name, prune=prune)
