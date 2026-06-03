"""Resolve a class metric on demand: run its stored parameterized query live and
return the value. The metric data stays in the relational source — the graph holds
only the ``MetricDef`` (connector + SQL + param map). Nothing is written to the graph
unless an optional per-node TTL cache is enabled on the metric.

Parameter binding reuses the same ``{path}`` template engine the trigger/workflow
layer uses, so a metric's ``param_map`` (e.g. ``{"cid": "{customer_id}"}``) reads the
anchor node exactly the way a trigger's ``parameter_map`` does. Values flow to the RDB
through the driver's bind machinery (see ``connectors``), never string-formatted into
the SQL, so a node-supplied value can never become SQL injection.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .connectors import fetch_rows
from .exceptions import TBoxNotFoundError
from .falkor_abox import _safe_identifier
from .models import MetricDef
from .workflows import _interpolate

# Reserved node property holding cached metric results: {metric_name: {value, at}}.
METRICS_CACHE_PROP = "metricsCache"


def resolve_metric(
    *,
    repo: Any,
    graph: Any,
    metric_name: str,
    node: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    use_cache: bool = True,
    now: str | None = None,
) -> Any:
    """Resolve ``metric_name`` against its RDB source and return the value.

    ``node`` is the anchor node's property map; ``MetricDef.param_map`` templates are
    interpolated against it. ``params`` are explicit bind values that override the
    interpolated ones. Shaping follows ``MetricDef.result_kind``: ``"scalar"`` returns
    the ``value_column`` of the first row, ``"row"`` the first row as a dict, ``"rows"``
    every row. When the metric has ``ttl_seconds`` set and the node carries a ``uuid``,
    a fresh cached value is returned without hitting the RDB, and a fresh fetch is
    written back to the node's cache.
    """
    metric = repo.get_metric(metric_name)
    if metric is None:
        raise TBoxNotFoundError(f"MetricDef not found: {metric_name}")
    connector = repo.get_connector(metric.connector_name)
    if connector is None:
        raise TBoxNotFoundError(f"ConnectorDef not found: {metric.connector_name}")

    # 1. Build bind params: param_map templates interpolated against the node, then
    #    explicit params override.
    bind: dict[str, Any] = {
        key: _interpolate(template, node or {}) for key, template in metric.param_map.items()
    }
    if params:
        bind.update(params)

    cacheable = bool(use_cache and metric.ttl_seconds and node and node.get("uuid"))
    current_now = now or datetime.now(timezone.utc).isoformat()

    # 2. Serve from the per-node cache when still fresh.
    if cacheable and node is not None:
        cached = _read_cache(node, metric, current_now)
        if cached is not _CACHE_MISS:
            return cached

    # 3. Live fetch — values always bound by the driver (injection-safe).
    rows = fetch_rows(connector, metric.sql, bind)
    value = _shape(rows, metric)

    if cacheable and node is not None:
        _write_cache(graph, metric, node, value, current_now)
    return value


def _shape(rows: list[dict[str, Any]], metric: MetricDef) -> Any:
    if metric.result_kind == "scalar":
        return rows[0].get(metric.value_column) if rows else None
    if metric.result_kind == "row":
        return rows[0] if rows else None
    return rows


# Sentinel so a cached ``None`` (a legitimately empty metric) is distinguishable from
# "no usable cache entry".
_CACHE_MISS = object()


def _load_cache(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return dict(raw)


def _read_cache(node: dict[str, Any], metric: MetricDef, now: str) -> Any:
    entry = _load_cache(node.get(METRICS_CACHE_PROP)).get(metric.name)
    if not isinstance(entry, dict) or "at" not in entry:
        return _CACHE_MISS
    try:
        age = (datetime.fromisoformat(now) - datetime.fromisoformat(entry["at"])).total_seconds()
    except (TypeError, ValueError):
        return _CACHE_MISS
    if 0 <= age <= (metric.ttl_seconds or 0):
        return entry.get("value")
    return _CACHE_MISS


def _write_cache(
    graph: Any, metric: MetricDef, node: dict[str, Any], value: Any, now: str
) -> None:
    label = _safe_identifier(metric.class_name, "class")
    # Read the node's current cache fresh so concurrent metrics on the same node do not
    # clobber each other's entries.
    rows = graph.query(
        f"MATCH (n:{label} {{uuid: $uuid}}) RETURN n.{METRICS_CACHE_PROP}",
        {"uuid": node["uuid"]},
    ).result_set
    cache = _load_cache(rows[0][0]) if rows and rows[0] else {}
    cache[metric.name] = {"value": value, "at": now}
    graph.query(
        f"MATCH (n:{label} {{uuid: $uuid}}) SET n.{METRICS_CACHE_PROP} = $cache",
        {"uuid": node["uuid"], "cache": json.dumps(cache, ensure_ascii=False)},
    )
