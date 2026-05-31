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
from .falkor_abox import _safe_identifier, upsert_abox_node
from .models import MaterializeResult, SourceBinding
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

    for props in mapped:
        props[SYNCED_AT_PROP] = synced_at
        props[SOURCE_CONNECTOR_PROP] = connector.name
        upsert_abox_node(
            graph=graph,
            class_name=class_name,
            uuid=str(uuid4()),
            properties=props,
        )

    return MaterializeResult(
        class_name=class_name,
        connector_name=connector.name,
        rows_fetched=len(rows),
        nodes_upserted=len(mapped),
        nodes_pruned=nodes_pruned,
        synced_at=synced_at,
    )


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
