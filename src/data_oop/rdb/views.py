"""Resolve a class view on demand: run its stored parameterized query live and return
the rows. The data stays in the relational source — the graph holds only the
``ViewDef`` (connector + SQL + accepted filters). Nothing is written to the graph; an
optional Redis result cache (keyed by view + filters, TTL from the ``ViewDef``) lives in
the same FalkorDB/Redis instance.

A view runs **once** and lets the RDB do any aggregation in a single query, so listing or
aggregating across many entities never fans out into N round-trips — a single-entity
lookup is just the same view filtered down to one key.

Filter values flow to the RDB through the driver's bind machinery (see ``connectors``),
never string-formatted into the SQL, so a caller-supplied value can never become SQL
injection.
"""

from __future__ import annotations

from typing import Any

from data_oop.rdb.cache import cache_get, cache_set, redis_from_graph, view_cache_key
from data_oop.rdb.connectors import fetch_rows
from data_oop.exceptions import TBoxNotFoundError


def resolve_view(
    *,
    repo: Any,
    graph: Any,
    view_name: str,
    filters: dict[str, Any] | None = None,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """Resolve ``view_name`` against its RDB source and return its rows.

    ``filters`` supply bind values for the view's ``:name`` placeholders; a declared
    ``required`` param must be present. When the view has ``ttl_seconds`` set, a fresh
    cached result is returned without hitting the RDB, and a fresh fetch is written back
    to the Redis cache that lives in the same FalkorDB instance.
    """
    view = repo.get_view(view_name)
    if view is None:
        raise TBoxNotFoundError(f"ViewDef not found: {view_name}")
    connector = repo.get_connector(view.connector_name)
    if connector is None:
        raise TBoxNotFoundError(f"ConnectorDef not found: {view.connector_name}")

    bind = dict(filters or {})
    missing = [p.name for p in view.params if p.required and p.name not in bind]
    if missing:
        raise ValueError(
            f"View '{view_name}' missing required filters: {', '.join(missing)}"
        )

    cacheable = bool(use_cache and view.ttl_seconds)
    redis = redis_from_graph(graph) if cacheable else None
    key = None
    if cacheable and redis is not None:
        key = view_cache_key(getattr(graph, "name", "data_oop"), view_name, bind)
        cached = cache_get(redis, key)
        if cached is not None:
            return cached

    # Live fetch — values always bound by the driver (injection-safe).
    rows = fetch_rows(connector, view.sql, bind)

    if cacheable and redis is not None and key is not None:
        cache_set(redis, key, rows, view.ttl_seconds)
    return rows


def connect_and_resolve_view(
    *,
    view_name: str,
    filters: dict[str, Any] | None = None,
    use_cache: bool = True,
    graph_name: str = "data_oop",
    host: str = "localhost",
    port: int = 6380,
    username: str | None = None,
    password: str | None = None,
) -> list[dict[str, Any]]:
    """Connect to FalkorDB and resolve a view in one call. Convenience wrapper for SDK
    consumers that do not already hold a graph handle."""
    from falkordb import FalkorDB

    from data_oop.falkor.repository import FalkorTBoxRepository

    db = FalkorDB(host=host, port=port, username=username, password=password)
    graph = db.select_graph(graph_name)
    repo = FalkorTBoxRepository(graph)
    return resolve_view(
        repo=repo,
        graph=graph,
        view_name=view_name,
        filters=filters,
        use_cache=use_cache,
    )
