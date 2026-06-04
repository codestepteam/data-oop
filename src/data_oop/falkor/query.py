"""Read-only ABox query for SDK / MCP consumers.

Runs an arbitrary Cypher query against the graph through FalkorDB's native read-only
``GRAPH.RO_QUERY``, which rejects any write (CREATE / MERGE / SET / DELETE / ...) at the
database level — safer than scanning the query text. Results come back as a list of row
dicts keyed by the RETURN column names, with node/edge values flattened to their
property maps so an LLM consumer gets plain JSON. A ``LIMIT`` is appended when the query
has none, so result size stays bounded.
"""

from __future__ import annotations

import re
from typing import Any

DEFAULT_LIMIT = 100
MAX_LIMIT = 500

_LIMIT_RE = re.compile(r"\blimit\b\s+\d+", re.IGNORECASE)


def _serialize_value(value: Any) -> Any:
    """Flatten a falkordb Node/Edge to its property map (+ labels) so rows are plain
    JSON. Scalars, maps and lists pass through (lists recurse)."""
    props = getattr(value, "properties", None)
    if props is not None and not isinstance(value, dict):
        out = dict(props)
        labels = getattr(value, "labels", None)
        if labels:
            out.setdefault("_labels", [labels] if isinstance(labels, str) else list(labels))
        return out
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    return value


def _column_names(result: Any, width: int) -> list[str]:
    """Best-effort RETURN-column names from the query result header, falling back to
    ``col0``, ``col1`` ... when the header cannot be read."""
    header = getattr(result, "header", None) or []
    names: list[str] = []
    for i in range(width):
        name = None
        if i < len(header):
            col = header[i]
            if isinstance(col, (list, tuple)) and len(col) >= 2:
                name = col[1]
            elif isinstance(col, (bytes, str)):
                name = col
        if isinstance(name, bytes):
            name = name.decode()
        names.append(name or f"col{i}")
    return names


def _ensure_limit(cypher: str, limit: int) -> str:
    limit = max(1, min(limit, MAX_LIMIT))
    if _LIMIT_RE.search(cypher):
        return cypher
    return f"{cypher.rstrip().rstrip(';')}\nLIMIT {limit}"


def abox_query(
    graph: Any,
    cypher: str,
    *,
    limit: int = DEFAULT_LIMIT,
    params: dict[str, Any] | None = None,
    timeout_ms: int | None = None,
) -> list[dict[str, Any]]:
    """Run a read-only Cypher query and return rows as a list of dicts.

    Writes are rejected by FalkorDB's read-only execution mode. A ``LIMIT`` is appended
    when the query has none (capped at :data:`MAX_LIMIT`). Node and edge values are
    flattened to their property maps. Rows are keyed by RETURN column names.
    """
    q = _ensure_limit(cypher, limit)
    # Native read-only execution rejects any write at the DB level. Fall back to plain
    # query only for non-FalkorDB graph stand-ins (e.g. test fakes) that lack ro_query.
    runner = getattr(graph, "ro_query", None) or graph.query
    result = runner(q, params or {}, timeout=timeout_ms) if timeout_ms else runner(q, params or {})
    rows = list(getattr(result, "result_set", []) or [])
    if not rows:
        return []
    width = max(len(r) for r in rows)
    cols = _column_names(result, width)
    return [
        {cols[i]: _serialize_value(row[i]) for i in range(len(row))}
        for row in rows
    ]


def connect_and_abox_query(
    cypher: str,
    *,
    limit: int = DEFAULT_LIMIT,
    params: dict[str, Any] | None = None,
    timeout_ms: int | None = None,
    graph_name: str = "data_oop",
    host: str = "localhost",
    port: int = 6380,
    username: str | None = None,
    password: str | None = None,
) -> list[dict[str, Any]]:
    """Connect to FalkorDB and run a read-only ABox query in one call. Convenience
    wrapper for SDK consumers that do not already hold a graph handle."""
    from falkordb import FalkorDB

    db = FalkorDB(host=host, port=port, username=username, password=password)
    graph = db.select_graph(graph_name)
    return abox_query(graph, cypher, limit=limit, params=params, timeout_ms=timeout_ms)
